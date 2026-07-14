"""Helm chart parser.

Not yet implemented — a scaffolding placeholder mirroring
:class:`~gitops_scaffold.parsers.compose.ComposeParser`. Note: this parser is
for *reading* an existing Helm chart as an application definition; generating
Helm charts as *output* remains explicitly out of scope (see
``docs/roadmap.md``, "explicitly out of scope for 1.0").
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.parsers.base import Parser


class HelmParser(Parser):
    """Parses a Helm chart's ``Chart.yaml`` into an :class:`ApplicationDefinition`."""

    format_name = "helm"

    def can_parse(self, path: Path) -> bool:
        return path.name == "Chart.yaml"

    def parse(self, path: Path) -> ApplicationDefinition:
        raise NotImplementedError(
            "Helm chart parsing is not yet implemented — see docs/roadmap.md."
        )
