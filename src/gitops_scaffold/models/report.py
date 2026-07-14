"""The stable, serializable envelope for a full analysis run.

This is exactly what ``gitops-scaffold analyze --format json`` prints and
what ``--output`` writes to disk. ``schema_version`` lets future consumers
(starting with ``generate`` in v0.3, which is expected to accept this exact
shape instead of re-parsing a Compose file) detect breaking changes.
Deliberately has no timestamps or other non-deterministic fields, so it can
be diffed byte-for-byte in golden-file tests.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition


class AnalysisReport(BaseModel):
    """A complete, self-contained analysis: the parsed application plus its findings."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    application: ApplicationDefinition
    analysis: AnalysisResult
