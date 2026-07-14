"""The output of running generators over an :class:`ApplicationDefinition`."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gitops_scaffold.models.analysis import AnalysisResult


class GeneratedFile(BaseModel):
    """A single file produced by a generator, not yet written to disk.

    ``requires_review`` is set whenever the generator had to fall back to a
    ``TODO`` / ``REVIEW REQUIRED`` placeholder instead of a confidently
    inferred value, so the CLI can surface an aggregate "N files need review"
    summary after generation.
    """

    model_config = ConfigDict(frozen=True)

    relative_path: Path
    content: str
    requires_review: bool = False


class GenerationResult(BaseModel):
    """Everything produced by generating manifests for one application."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    output_dir: Path
    files: tuple[GeneratedFile, ...] = Field(default_factory=tuple)
    analysis: AnalysisResult

    @property
    def files_requiring_review(self) -> tuple[GeneratedFile, ...]:
        return tuple(f for f in self.files if f.requires_review)
