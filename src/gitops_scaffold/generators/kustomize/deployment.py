"""Generates the Kubernetes ``Deployment`` manifest for each service.

Scaffolding placeholder — implementation lands in v0.3 Component 5 (see
``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class DeploymentGenerator(ManifestGenerator):
    kind = "Deployment"

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        raise NotImplementedError
