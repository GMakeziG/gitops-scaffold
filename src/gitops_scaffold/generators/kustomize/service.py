"""Generates the ``v1`` ``ClusterIP`` ``Service`` manifest for services that expose ports.

Renders ``templates/service.yaml.j2``. Selector labels come from the exact
same :func:`~gitops_scaffold.generators.labels.pod_selector_labels` call the
Deployment generator uses, and each port's name is the exact same value
:class:`~gitops_scaffold.generators.kustomize.deployment.DeploymentGenerator`
renders as ``containerPort.name`` — both guarantee "Service selector/targetPort
match the Deployment" structurally rather than by convention.
"""

from __future__ import annotations

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.labels import pod_selector_labels, standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.ports import plan_ports
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.utils.naming import k8s_resource_name


class ServiceGenerator(ManifestGenerator):
    kind = "Service"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files: list[GeneratedFile] = []
        notes: list[GenerationNote] = []
        total_services = len(app.services)

        for service in app.services:
            if service.image is None:
                continue  # DeploymentGenerator already records this skip once.

            # Deliberately NOT re-adding port_plan.notes here: DeploymentGenerator
            # calls this exact same pure function on the same inputs and already
            # surfaces its notes once. Both generators computing the identical
            # plan is fine; both *reporting* it would double the same observation.
            port_plan = plan_ports(service, self._settings)

            if not port_plan.ports:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.SKIPPED,
                        message=f"No Service generated for '{service.name}': it exposes no ports.",
                        service_name=service.name,
                    )
                )
                continue

            resource_name = k8s_resource_name(service.name)
            content = render_template(
                "service.yaml.j2",
                resource_name=resource_name,
                namespace=self._settings.default_namespace,
                labels=standard_labels(service, app, self._settings),
                selector_labels=pod_selector_labels(service, app),
                service_type=self._settings.service_type,
                ports=port_plan.ports,
            )
            files.append(
                GeneratedFile(
                    relative_path=resource_path(service.name, "service.yaml", total_services),
                    content=content,
                )
            )

        return GenerationOutcome(files=tuple(files), notes=tuple(notes))
