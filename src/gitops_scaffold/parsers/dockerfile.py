"""Dockerfile parser.

Not yet implemented — a scaffolding placeholder mirroring
:class:`~gitops_scaffold.parsers.compose.ComposeParser`. Planned for a
post-v0.2 milestone (Dockerfile-only projects, no Compose file present); see
``docs/roadmap.md``.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.parsers.base import Parser


class DockerfileParser(Parser):
    """Parses a standalone ``Dockerfile`` into an :class:`ApplicationDefinition`."""

    format_name = "dockerfile"

    def can_parse(self, path: Path) -> bool:
        return path.name == "Dockerfile" or path.name.endswith(".dockerfile")

    def parse(self, path: Path) -> ApplicationDefinition:
        raise NotImplementedError(
            "Dockerfile parsing is not yet implemented — see docs/roadmap.md."
        )
