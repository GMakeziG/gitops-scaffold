"""Generates the top-level ``kustomization.yaml`` tying all generated resources together.

Scaffolding placeholder — implementation lands in v0.3 Component 8 (see
``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class KustomizationGenerator(ManifestGenerator):
    kind = "Kustomization"

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        raise NotImplementedError
