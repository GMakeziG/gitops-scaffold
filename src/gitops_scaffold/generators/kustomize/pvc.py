"""Generates ``PersistentVolumeClaim`` manifests for services that need storage.

Renders ``templates/pvc.yaml.j2``. Storage size is never guessed — when it
can't be inferred, the rendered PVC contains a ``REVIEW REQUIRED`` marker
instead of a default capacity. Scaffolding placeholder — see
``docs/roadmap.md`` (v0.2/v0.3).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GeneratedFile


class PersistentVolumeClaimGenerator(ManifestGenerator):
    kind = "PersistentVolumeClaim"

    def generate(
        self, app: ApplicationDefinition, analysis: AnalysisResult
    ) -> tuple[GeneratedFile, ...]:
        raise NotImplementedError
