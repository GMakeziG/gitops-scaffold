"""Generates ``PersistentVolumeClaim`` manifests for services that need storage.

Storage size is never guessed — every generated PVC is marked
``REVIEW REQUIRED`` since Compose has no size concept at all (see
``generators/volumes.py`` for the eligibility rules: named volumes, plus
bind mounts and anonymous volumes that don't look like host-system paths or
single config files). Renders ``templates/pvc.yaml.j2``, one file per
location (root for volumes shared by 2+ services, per-service otherwise)
containing one or more ``---``-separated PVC documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.labels import standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.generators.volumes import PlannedPVC, plan_volumes
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition
from gitops_scaffold.models.generation import GeneratedFile, GenerationOutcome
from gitops_scaffold.utils.naming import kebab_case


@dataclass(frozen=True)
class _PvcContext:
    name: str
    target: str
    source_description: str
    labels: dict[str, str]


class PersistentVolumeClaimGenerator(ManifestGenerator):
    kind = "PersistentVolumeClaim"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files: list[GeneratedFile] = []
        # plan_volumes() is also called by DeploymentGenerator (to build
        # volumeMounts), but only this generator surfaces its notes -- it
        # owns the "here's what happened to each volume" story.
        volume_plan = plan_volumes(app, self._settings)
        total_services = len(app.services)
        services_by_name = {service.name: service for service in app.services}

        if volume_plan.shared_pvcs:
            content = self._render(volume_plan.shared_pvcs, app, services_by_name)
            files.append(
                GeneratedFile(relative_path=Path("pvc.yaml"), content=content, requires_review=True)
            )

        for service in app.services:
            if service.image is None:
                continue
            pvcs = volume_plan.service_pvcs.get(service.name, ())
            if not pvcs:
                continue
            content = self._render(pvcs, app, services_by_name)
            files.append(
                GeneratedFile(
                    relative_path=resource_path(service.name, "pvc.yaml", total_services),
                    content=content,
                    requires_review=True,
                )
            )

        return GenerationOutcome(files=tuple(files), notes=volume_plan.notes)

    def _render(
        self,
        pvcs: tuple[PlannedPVC, ...],
        app: ApplicationDefinition,
        services_by_name: dict[str, ServiceDefinition],
    ) -> str:
        contexts = [
            _PvcContext(
                name=pvc.name,
                target=pvc.target,
                source_description=pvc.source_description,
                labels=_pvc_labels(pvc, app, self._settings, services_by_name),
            )
            for pvc in pvcs
        ]
        return render_template(
            "pvc.yaml.j2",
            pvcs=contexts,
            namespace=self._settings.default_namespace,
            access_mode=self._settings.default_access_mode,
            size=self._settings.default_pvc_size,
        )


def _pvc_labels(
    pvc: PlannedPVC,
    app: ApplicationDefinition,
    settings: ScaffoldSettings,
    services_by_name: dict[str, ServiceDefinition],
) -> dict[str, str]:
    if len(pvc.service_names) == 1:
        return standard_labels(services_by_name[pvc.service_names[0]], app, settings)
    # A PVC shared by more than one service isn't scoped to any single
    # service's identity, so it gets no app.kubernetes.io/name label.
    return {
        "app.kubernetes.io/part-of": kebab_case(app.name),
        "app.kubernetes.io/managed-by": "gitops-scaffold",
        **settings.additional_labels,
    }
