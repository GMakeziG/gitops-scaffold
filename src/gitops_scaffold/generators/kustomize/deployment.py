"""Generates the ``apps/v1`` ``Deployment`` manifest for each service.

Renders ``templates/deployment.yaml.j2``. See ``docs/generation.md`` for the
full Compose → Kubernetes mapping this generator implements, in particular
the (easy to get backwards) ``entrypoint``/``command`` ↔ ``command``/``args``
mapping and the healthcheck → probe translation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.healthcheck import (
    plan_readiness_or_liveness_probe,
    plan_startup_probe,
)
from gitops_scaffold.generators.kustomize.configmap import has_configmap_data
from gitops_scaffold.generators.labels import pod_selector_labels, standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.ports import plan_ports
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.generators.secret_classification import is_optional, secret_classifications
from gitops_scaffold.generators.volumes import VolumePlan, plan_volumes
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.utils.naming import k8s_resource_name

#: Compose and Kubernetes memory quantities overlap enough in practice
#: ("512M", "1Gi", "256K", ...) that they can pass through as-is when they
#: match this shape; anything else is flagged for review rather than
#: guessed at.
_K8S_QUANTITY_PATTERN = re.compile(r"(?i)^\d+(\.\d+)?(e|p|t|g|m|k)?i?$")

_IMAGE_TAG_FINDING_CODES = frozenset({"image-tag-missing", "image-tag-latest"})


@dataclass(frozen=True)
class _SecretEnvEntry:
    name: str
    secret_name: str
    optional: bool


@dataclass(frozen=True)
class _PodVolume:
    name: str
    pvc_name: str


@dataclass(frozen=True)
class _VolumeMountEntry:
    name: str
    target: str
    read_only: bool


@dataclass(frozen=True)
class _SecurityContext:
    uid: int
    gid: int | None


class DeploymentGenerator(ManifestGenerator):
    kind = "Deployment"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files: list[GeneratedFile] = []
        notes: list[GenerationNote] = []
        total_services = len(app.services)
        volume_plan = plan_volumes(app, self._settings)

        for service in app.services:
            if service.image is None:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.SKIPPED,
                        message=(
                            f"No Deployment (or any other manifest) generated for service "
                            f"'{service.name}': it has no image."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )
                continue

            resource_name = k8s_resource_name(service.name)
            secret_names = secret_classifications(service.name, analysis)

            command, args = _command_and_args(service)
            image_review_reason = _image_review_reason(service, analysis)
            port_plan = plan_ports(service, self._settings)
            notes.extend(port_plan.notes)

            configmap_name = (
                k8s_resource_name(service.name, "config")
                if has_configmap_data(service, secret_names)
                else None
            )
            secret_resource_name = k8s_resource_name(service.name, "secret")
            secret_env_entries = [
                _SecretEnvEntry(
                    name=var_name, secret_name=secret_resource_name, optional=is_optional(code)
                )
                for var_name, code in sorted(secret_names.items())
            ]

            volume_mounts, pod_volumes = _pod_volumes(service.name, volume_plan)

            security_context, security_context_reason = _security_context(service)

            readiness_probe = None
            liveness_probe = None
            startup_probe = None
            # Three distinct states, not two: no healthcheck declared at all
            # (health_check_missing -- a TODO, review required), an explicit
            # opt-out (disabled -- a plain informational note, not review
            # required), and present+enabled (probes rendered).
            health_check_missing = service.health_check is None
            health_check_disabled = (
                service.health_check is not None and service.health_check.disabled
            )

            if service.health_check is not None and not service.health_check.disabled:
                readiness_probe = plan_readiness_or_liveness_probe(service.health_check)
                if self._settings.enable_liveness_probe:
                    liveness_probe = readiness_probe
                startup_probe, used_fallback = plan_startup_probe(service.health_check)
                if used_fallback:
                    notes.append(
                        GenerationNote(
                            category=GenerationNoteCategory.ASSUMPTION,
                            message=(
                                f"Service '{service.name}': no healthcheck interval was declared, "
                                "so the generated startupProbe uses a 10-second fallback cadence."
                            ),
                            service_name=service.name,
                        )
                    )
            elif health_check_disabled:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Service '{service.name}' explicitly disables its health check — "
                            "no probes generated (this was a deliberate Compose opt-out, not an "
                            "oversight)."
                        ),
                        service_name=service.name,
                    )
                )

            resources_requests, resources_limits, resource_notes = _resources(
                service, self._settings
            )
            notes.extend(resource_notes)

            content_kwargs = {
                "resource_name": resource_name,
                "namespace": self._settings.default_namespace,
                "labels": standard_labels(service, app, self._settings),
                "selector_labels": pod_selector_labels(service, app),
                "image": service.image,
                "image_review_reason": image_review_reason,
                "image_pull_policy": self._settings.image_pull_policy,
                "command": command,
                "args": args,
                "ports": port_plan.ports,
                "configmap_name": configmap_name,
                "secret_env_entries": secret_env_entries,
                "volume_mounts": volume_mounts,
                "pod_volumes": pod_volumes,
                "readiness_probe": readiness_probe,
                "liveness_probe": liveness_probe,
                "startup_probe": startup_probe,
                "health_check_missing": health_check_missing,
                "resources_requests": resources_requests,
                "resources_limits": resources_limits,
                "security_context": security_context,
                "security_context_reason": security_context_reason,
            }

            content = render_template("deployment.yaml.j2", **content_kwargs)

            requires_review = bool(
                image_review_reason
                or security_context_reason
                or health_check_missing
                or resource_notes
                or secret_env_entries
            )
            files.append(
                GeneratedFile(
                    relative_path=resource_path(service.name, "deployment.yaml", total_services),
                    content=content,
                    requires_review=requires_review,
                )
            )

            if image_review_reason:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=f"Service '{service.name}': {image_review_reason}.",
                        service_name=service.name,
                        requires_review=True,
                    )
                )
            if security_context_reason:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=f"Service '{service.name}': {security_context_reason}.",
                        service_name=service.name,
                        requires_review=True,
                    )
                )
            if health_check_missing:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Service '{service.name}': no health check was detected. Add a "
                            "readiness/liveness probe manually."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )
            if service.restart_policy:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.WARNING,
                        message=(
                            f"Service '{service.name}' declared Compose restart policy "
                            f"'{service.restart_policy}' — this has no direct Deployment "
                            "equivalent and is not rendered as any field. Deployments always "
                            "maintain the desired replica count regardless of this setting."
                        ),
                        service_name=service.name,
                    )
                )

        return GenerationOutcome(files=tuple(files), notes=tuple(notes))


def _command_and_args(
    service: ServiceDefinition,
) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None]:
    """Compose ``entrypoint`` -> Deployment ``command``; Compose ``command`` -> ``args``.

    This is the only mapping that reproduces Docker's actual behavior when
    ``entrypoint`` is overridden without ``command`` (the image's default CMD
    is dropped entirely, not appended) — not just the common case of neither
    or both being set.
    """
    return service.entrypoint, service.command


def _image_review_reason(service: ServiceDefinition, analysis: AnalysisResult) -> str | None:
    for finding in analysis.findings:
        if finding.service_name == service.name and finding.code in _IMAGE_TAG_FINDING_CODES:
            return finding.message
    return None


def _security_context(service: ServiceDefinition) -> tuple[_SecurityContext | None, str | None]:
    user = service.runtime_user
    if user is None:
        return None, "runtime user could not be determined; set securityContext explicitly"
    if user.uid is None:
        return (
            None,
            f"user was declared by name ('{user.raw}'); numeric UID/GID could not be "
            "resolved without inspecting the image",
        )
    return _SecurityContext(uid=user.uid, gid=user.gid), None


def _looks_like_k8s_quantity(value: str) -> bool:
    return bool(_K8S_QUANTITY_PATTERN.match(value))


def _resources(
    service: ServiceDefinition, settings: ScaffoldSettings
) -> tuple[dict[str, str] | None, dict[str, str] | None, list[GenerationNote]]:
    notes: list[GenerationNote] = []
    resources = service.resources

    def _value(compose_value: str | None, default: str | None, field: str) -> str | None:
        if compose_value is not None:
            if "memory" in field and not _looks_like_k8s_quantity(compose_value):
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Service '{service.name}': {field} value '{compose_value}' doesn't "
                            "look like a Kubernetes quantity — review before applying."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )
            return compose_value
        return default

    cpu_request = _value(
        resources.cpu_request if resources else None, settings.default_cpu_request, "cpu request"
    )
    cpu_limit = _value(
        resources.cpu_limit if resources else None, settings.default_cpu_limit, "cpu limit"
    )
    memory_request = _value(
        resources.memory_request if resources else None,
        settings.default_memory_request,
        "memory request",
    )
    memory_limit = _value(
        resources.memory_limit if resources else None, settings.default_memory_limit, "memory limit"
    )

    requests = {}
    if cpu_request:
        requests["cpu"] = cpu_request
    if memory_request:
        requests["memory"] = memory_request
    limits = {}
    if cpu_limit:
        limits["cpu"] = cpu_limit
    if memory_limit:
        limits["memory"] = memory_limit

    return (requests or None, limits or None, notes)


def _pod_volumes(
    service_name: str, volume_plan: VolumePlan
) -> tuple[tuple[_VolumeMountEntry, ...], tuple[_PodVolume, ...]]:
    mounts = volume_plan.service_mounts.get(service_name, ())

    volume_mounts = tuple(
        _VolumeMountEntry(name=mount.pvc_name, target=mount.target, read_only=mount.read_only)
        for mount in mounts
    )
    seen: set[str] = set()
    pod_volumes: list[_PodVolume] = []
    for mount in mounts:
        if mount.pvc_name in seen:
            continue
        seen.add(mount.pvc_name)
        pod_volumes.append(_PodVolume(name=mount.pvc_name, pvc_name=mount.pvc_name))

    return volume_mounts, tuple(pod_volumes)
