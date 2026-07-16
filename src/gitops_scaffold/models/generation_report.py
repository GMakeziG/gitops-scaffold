"""The stable, serializable summary of one ``generate`` run.

This is exactly what ``generation-report.json`` contains. Deliberately does
**not** re-embed the (possibly secret-bearing) :class:`ApplicationDefinition`
at all — only the scalar ``application_name``/``namespace`` — so "never
includes secret values" is true by construction rather than depending on a
redaction call. ``analysis`` embeds :class:`AnalysisResult` verbatim, which
is safe: no ``Finding.message`` ever contains a secret value (an invariant
``analyzer/rules/secrets.py`` maintains). No timestamp field anywhere — the
simplest way to keep golden-file diffs byte-stable across runs.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.generation import GenerationNote, GenerationNoteCategory


class GenerationReport(BaseModel):
    """Everything produced by generating manifests for one application."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    generator_version: str
    application_name: str
    namespace: str
    confidence: float = Field(ge=0.0, le=1.0)
    generated_files: tuple[str, ...] = Field(default_factory=tuple)
    files_requiring_review: tuple[str, ...] = Field(default_factory=tuple)
    notes: tuple[GenerationNote, ...] = Field(default_factory=tuple)
    overwritten_files: tuple[str, ...] = Field(default_factory=tuple)
    orphaned_files: tuple[str, ...] = Field(default_factory=tuple)
    analysis: AnalysisResult

    @property
    def assumptions(self) -> tuple[GenerationNote, ...]:
        return tuple(n for n in self.notes if n.category is GenerationNoteCategory.ASSUMPTION)

    @property
    def skipped(self) -> tuple[GenerationNote, ...]:
        return tuple(n for n in self.notes if n.category is GenerationNoteCategory.SKIPPED)

    @property
    def warnings(self) -> tuple[GenerationNote, ...]:
        return tuple(n for n in self.notes if n.category is GenerationNoteCategory.WARNING)
