"""Generates the Kubernetes ``Ingress`` manifest — optional, off by default.

Only ever produces anything when an :class:`~gitops_scaffold.generators.ingress_config.IngressConfig`
is supplied (which only happens when the CLI's four ``--ingress-*`` flags
are all given together — see ``cli.py``). Applies to the first service (in
declaration order) that has a Service generated; with more than one
candidate, only the first gets an Ingress and a note explains the choice
rather than silently picking one. Renders ``templates/ingress.yaml.j2``.
"""

from __future__ import annotations

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.ingress_config import IngressConfig
from gitops_scaffold.generators.labels import standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.ports import PortPlan, plan_ports
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.utils.naming import k8s_resource_name


def ingress_candidates(
    app: ApplicationDefinition, settings: ScaffoldSettings
) -> list[tuple[ServiceDefinition, PortPlan]]:
    """Every (service, port_plan) that could receive an Ingress, in declaration order.

    Shared with :class:`~gitops_scaffold.generators.kustomize.kustomization.KustomizationGenerator`,
    which needs to know the exact same "which service gets the Ingress"
    decision to list ``ingress.yaml`` in the right place.
    """
    candidates = []
    for service in app.services:
        if service.image is None:
            continue
        port_plan = plan_ports(service, settings)
        if port_plan.ports:
            candidates.append((service, port_plan))
    return candidates


class IngressGenerator(ManifestGenerator):
    kind = "Ingress"

    def __init__(
        self,
        settings: ScaffoldSettings | None = None,
        ingress_config: IngressConfig | None = None,
    ) -> None:
        self._settings = settings or ScaffoldSettings()
        self._ingress_config = ingress_config

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        if self._ingress_config is None:
            return GenerationOutcome()

        total_services = len(app.services)
        candidates = ingress_candidates(app, self._settings)

        if not candidates:
            return GenerationOutcome(
                notes=(
                    GenerationNote(
                        category=GenerationNoteCategory.SKIPPED,
                        message="Ingress was requested but no service exposes any port.",
                        requires_review=True,
                    ),
                )
            )

        service, port_plan = candidates[0]
        notes: list[GenerationNote] = []
        if len(candidates) > 1:
            others = ", ".join(other.name for other, _ in candidates[1:])
            notes.append(
                GenerationNote(
                    category=GenerationNoteCategory.WARNING,
                    message=(
                        f"Ingress generated only for '{service.name}' (the first service with a "
                        f"port); other candidates ({others}) were not given one — generate "
                        "additional Ingress manifests by hand if needed."
                    ),
                    requires_review=True,
                )
            )

        resource_name = k8s_resource_name(service.name)
        content = render_template(
            "ingress.yaml.j2",
            resource_name=resource_name,
            namespace=self._settings.default_namespace,
            labels=standard_labels(service, app, self._settings),
            host=self._ingress_config.host,
            ingress_class=self._ingress_config.ingress_class,
            tls_secret=self._ingress_config.tls_secret,
            cluster_issuer=self._ingress_config.cluster_issuer,
            service_name=resource_name,
            port_name=port_plan.ports[0].name,
        )
        notes.append(
            GenerationNote(
                category=GenerationNoteCategory.ASSUMPTION,
                message=(
                    f"Ingress generated for '{service.name}' at host '{self._ingress_config.host}' "
                    f"— confirm DNS points here and that the cert-manager ClusterIssuer "
                    f"'{self._ingress_config.cluster_issuer}' exists."
                ),
                service_name=service.name,
                requires_review=True,
            )
        )
        return GenerationOutcome(
            files=(
                GeneratedFile(
                    relative_path=resource_path(service.name, "ingress.yaml", total_services),
                    content=content,
                    requires_review=True,
                ),
            ),
            notes=tuple(notes),
        )
