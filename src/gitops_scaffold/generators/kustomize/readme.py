"""Generates the output directory's ``README.md``.

Unlike every other generator, this one needs the *aggregated* notes from
every other generator that already ran (to list every "REVIEW REQUIRED"
item and everything that was skipped, across all services) — information no
single ``(app, analysis)`` call can reconstruct on its own, since note
*messages* are free-form prose each generator composes itself, not something
independently re-derivable from a pure predicate the way file-presence is
for :class:`~gitops_scaffold.generators.kustomize.kustomization.KustomizationGenerator`.
For that reason ``OutputReadmeGenerator`` deliberately does **not** implement
the :class:`~gitops_scaffold.generators.base.ManifestGenerator` interface —
its ``generate`` takes an extra ``notes`` parameter, and it's invoked
directly by the generation pipeline after every other generator has run,
rather than being one more entry in the pipeline's generic generator list.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitops_scaffold.config.settings import ScaffoldSettings
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


@dataclass(frozen=True)
class _ServiceContext:
    name: str
    skipped: bool
    skip_reason: str | None = None
    image: str | None = None
    ports_summary: str | None = None
    env_vars: list[tuple[str, str]] | None = None
    secret_name: str | None = None
    required_secret_keys: list[str] | None = None
    optional_secret_keys: list[str] | None = None
    secret_create_command: str | None = None
    volumes: list[tuple[str, str, str]] | None = None
    port_forward_command: str | None = None


class OutputReadmeGenerator:
    kind = "README"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(
        self,
        app: ApplicationDefinition,
        analysis: AnalysisResult,
        notes: tuple[GenerationNote, ...],
    ) -> GenerationOutcome:
        volume_plan = plan_volumes(app, self._settings)
        services = [
            self._service_context(service, analysis, volume_plan) for service in app.services
        ]

        review_items = [note.message for note in notes if note.requires_review]
        skipped_items = [
            note.message for note in notes if note.category is GenerationNoteCategory.SKIPPED
        ]

        content = render_template(
            "README.md.j2",
            app_name=app.name,
            source_path=app.source_path or "(unknown)",
            confidence_percent=analysis.confidence_percent,
            namespace=self._settings.default_namespace,
            services=services,
            review_items=review_items,
            skipped_items=skipped_items,
        )
        return GenerationOutcome(
            files=(GeneratedFile(relative_path=Path("README.md"), content=content),)
        )

    def _service_context(
        self,
        service: ServiceDefinition,
        analysis: AnalysisResult,
        volume_plan: VolumePlan,
    ) -> _ServiceContext:
        if service.image is None:
            return _ServiceContext(
                name=service.name,
                skipped=True,
                skip_reason="no image was detected for this service",
            )

        namespace = self._settings.default_namespace
        port_plan = plan_ports(service, self._settings)
        ports_summary = None
        port_forward_command = None
        if service.ports:
            parts = []
            for raw_port in service.ports:
                part = f"{raw_port.container_port}/{raw_port.protocol.value}"
                if raw_port.host_port:
                    part += f" (published on host port {raw_port.host_port} in Compose)"
                parts.append(part)
            ports_summary = ", ".join(parts)

            first_raw = service.ports[0]
            # Use the planned (post port_overrides) container port for the
            # actual remote side of the command -- the local side keeps
            # Compose's host port for familiarity, since only the local side
            # of port-forward is arbitrary/user-chosen.
            remote_port = port_plan.ports[0].container_port
            local_port = first_raw.host_port or remote_port
            resource_name = k8s_resource_name(service.name)
            port_forward_command = (
                f"kubectl port-forward -n {namespace} deploy/{resource_name} "
                f"{local_port}:{remote_port}"
            )

        env_vars = None
        secret_names = secret_classifications(service.name, analysis)
        non_secret_vars = [
            (var.name, var.value if var.value is not None else "")
            for var in service.environment
            if var.name not in secret_names
        ]
        if non_secret_vars:
            env_vars = non_secret_vars

        secret_name = None
        required_keys: list[str] | None = None
        optional_keys: list[str] | None = None
        secret_create_command = None
        if secret_names:
            secret_name = k8s_resource_name(service.name, "secret")
            required_keys = sorted(k for k, code in secret_names.items() if not is_optional(code))
            optional_keys = sorted(k for k, code in secret_names.items() if is_optional(code))
            secret_create_command = _build_secret_command(
                secret_name, namespace, required_keys, optional_keys
            )

        volumes = None
        mounts = volume_plan.service_mounts.get(service.name, ())
        if mounts:
            pvc_sizes = {
                pvc.name: self._settings.default_pvc_size for pvc in volume_plan.shared_pvcs
            }
            pvc_sizes.update(
                {
                    pvc.name: self._settings.default_pvc_size
                    for pvc in volume_plan.service_pvcs.get(service.name, ())
                }
            )
            volumes = [
                (
                    mount.target,
                    mount.pvc_name,
                    pvc_sizes.get(mount.pvc_name, self._settings.default_pvc_size),
                )
                for mount in mounts
            ]

        return _ServiceContext(
            name=service.name,
            skipped=False,
            image=service.image,
            ports_summary=ports_summary,
            env_vars=env_vars,
            secret_name=secret_name,
            required_secret_keys=required_keys,
            optional_secret_keys=optional_keys,
            secret_create_command=secret_create_command,
            volumes=volumes,
            port_forward_command=port_forward_command,
        )


def _build_secret_command(
    secret_name: str, namespace: str, required_keys: list[str], optional_keys: list[str]
) -> str:
    lines = [f"  kubectl create secret generic {secret_name} -n {namespace} \\"]
    all_keys = required_keys + optional_keys
    for index, key in enumerate(all_keys):
        suffix = " \\" if index < len(all_keys) - 1 else ""
        lines.append(f"    --from-literal={key}=CHANGE_ME{suffix}")
    return "\n".join(lines)
