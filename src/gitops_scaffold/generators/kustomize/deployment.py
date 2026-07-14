"""Generates the Kubernetes ``Deployment`` manifest for each service.

Renders ``templates/deployment.yaml.j2``. Scaffolding placeholder — see
``docs/roadmap.md`` (v0.2/v0.3).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GeneratedFile


class DeploymentGenerator(ManifestGenerator):
    kind = "Deployment"

    def generate(
        self, app: ApplicationDefinition, analysis: AnalysisResult
    ) -> tuple[GeneratedFile, ...]:
        raise NotImplementedError
