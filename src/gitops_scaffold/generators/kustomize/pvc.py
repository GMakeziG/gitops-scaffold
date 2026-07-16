"""Generates ``PersistentVolumeClaim`` manifests for services that need storage.

Storage size is never guessed — when it can't be inferred, the rendered PVC
contains a ``REVIEW REQUIRED`` marker instead of a default capacity.
Scaffolding placeholder — implementation lands in v0.3 Component 7 (see
``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class PersistentVolumeClaimGenerator(ManifestGenerator):
    kind = "PersistentVolumeClaim"

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        raise NotImplementedError
