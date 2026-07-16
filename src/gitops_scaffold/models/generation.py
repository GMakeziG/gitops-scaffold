"""The output of running generators over an :class:`ApplicationDefinition`."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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


class GenerationNoteCategory(StrEnum):
    """What kind of generation-time observation a :class:`GenerationNote` records."""

    #: A value was filled in with a confident default or a faithful
    #: translation choice — not a guess, but worth knowing about.
    ASSUMPTION = "assumption"
    #: A resource kind was deliberately not generated for a service (no
    #: image, no ports, an excluded bind mount, ...).
    SKIPPED = "skipped"
    #: Something the operator should be aware of that isn't tied to one
    #: specific generated value (e.g. Compose's restart policy has no
    #: Deployment equivalent).
    WARNING = "warning"


class GenerationNote(BaseModel):
    """A single human-readable observation from generation.

    ``requires_review=True`` marks an unresolved decision the operator must
    confirm before applying — this doubles as the "unresolved decisions"
    category rather than introducing a separate one, since in practice every
    unresolved decision is also an assumption that needs review.
    """

    model_config = ConfigDict(frozen=True)

    category: GenerationNoteCategory
    message: str
    service_name: str | None = None
    requires_review: bool = False


class GenerationOutcome(BaseModel):
    """Everything one :class:`~gitops_scaffold.generators.base.ManifestGenerator`
    produced for one application: files plus any notes about how it got there.
    """

    model_config = ConfigDict(frozen=True)

    files: tuple[GeneratedFile, ...] = Field(default_factory=tuple)
    notes: tuple[GenerationNote, ...] = Field(default_factory=tuple)
