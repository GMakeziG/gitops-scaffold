"""Generates ``VALIDATION_CHECKLIST.md``: every finding an operator must review before applying.

Renders ``templates/VALIDATION_CHECKLIST.md.j2``. Scaffolding placeholder —
see ``docs/roadmap.md`` (v0.2/v0.3).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GeneratedFile


class ValidationChecklistGenerator(ManifestGenerator):
    kind = "ValidationChecklist"

    def generate(
        self, app: ApplicationDefinition, analysis: AnalysisResult
    ) -> tuple[GeneratedFile, ...]:
        raise NotImplementedError
