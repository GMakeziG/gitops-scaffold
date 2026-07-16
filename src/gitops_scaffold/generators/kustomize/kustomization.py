"""Generates ``kustomization.yaml`` — one per service subdirectory in
multi-service mode, plus a root one that ties everything together.

Never lists ``secret.example.yaml``, ``README.md``, or
``generation-report.json``. This generator determines "would a ConfigMap /
Service / PVC exist for this service" the same way each of those generators
decides for themselves — by calling the exact same shared, deterministic
predicates (:func:`~gitops_scaffold.generators.kustomize.configmap.has_configmap_data`,
:func:`~gitops_scaffold.generators.ports.plan_ports`,
:func:`~gitops_scaffold.generators.volumes.plan_volumes`) rather than needing
any direct communication with those generators' actual output — since all of
those decisions are pure functions of ``(app, analysis, settings)``, the
exact same inputs this generator receives, there's no way for the two to
disagree.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.ingress_config import IngressConfig
from gitops_scaffold.generators.kustomize.configmap import has_configmap_data
from gitops_scaffold.generators.kustomize.ingress import ingress_candidates
from gitops_scaffold.generators.layout import is_multi_service
from gitops_scaffold.generators.ports import plan_ports
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.generators.secret_classification import secret_classifications
from gitops_scaffold.generators.volumes import plan_volumes
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GeneratedFile, GenerationOutcome
from gitops_scaffold.utils.naming import kebab_case

#: Fixed, deterministic order resources are listed in — doesn't affect
#: apply behavior (kubectl sorts by kind itself) but keeps the file readable
#: and diff-stable.
_RESOURCE_ORDER = ("configmap.yaml", "pvc.yaml", "deployment.yaml", "service.yaml", "ingress.yaml")


class KustomizationGenerator(ManifestGenerator):
    kind = "Kustomization"

    def __init__(
        self,
        settings: ScaffoldSettings | None = None,
        ingress_config: IngressConfig | None = None,
    ) -> None:
        self._settings = settings or ScaffoldSettings()
        self._ingress_config = ingress_config

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        volume_plan = plan_volumes(app, self._settings)
        multi = is_multi_service(len(app.services))

        ingress_service_name = None
        if self._ingress_config is not None:
            candidates = ingress_candidates(app, self._settings)
            if candidates:
                ingress_service_name = candidates[0][0].name

        service_resources: dict[str, list[str]] = {}
        for service in app.services:
            if service.image is None:
                continue
            present = set()
            secret_names = secret_classifications(service.name, analysis)
            if has_configmap_data(service, secret_names):
                present.add("configmap.yaml")
            if volume_plan.service_pvcs.get(service.name):
                present.add("pvc.yaml")
            present.add("deployment.yaml")
            if plan_ports(service, self._settings).ports:
                present.add("service.yaml")
            if service.name == ingress_service_name:
                present.add("ingress.yaml")
            service_resources[service.name] = [r for r in _RESOURCE_ORDER if r in present]

        files: list[GeneratedFile] = []

        if not multi:
            resources = next(iter(service_resources.values()), [])
            files.append(
                GeneratedFile(
                    relative_path=Path("kustomization.yaml"),
                    content=render_template(
                        "kustomization.yaml.j2",
                        namespace=self._settings.default_namespace,
                        resources=resources,
                    ),
                )
            )
            return GenerationOutcome(files=tuple(files))

        for service_name, resources in service_resources.items():
            files.append(
                GeneratedFile(
                    relative_path=Path(kebab_case(service_name)) / "kustomization.yaml",
                    content=render_template(
                        "kustomization.yaml.j2", namespace=None, resources=resources
                    ),
                )
            )

        root_resources = [kebab_case(name) for name in service_resources]
        if volume_plan.shared_pvcs:
            root_resources.append("pvc.yaml")
        files.append(
            GeneratedFile(
                relative_path=Path("kustomization.yaml"),
                content=render_template(
                    "kustomization.yaml.j2",
                    namespace=self._settings.default_namespace,
                    resources=root_resources,
                ),
            )
        )

        return GenerationOutcome(files=tuple(files))
