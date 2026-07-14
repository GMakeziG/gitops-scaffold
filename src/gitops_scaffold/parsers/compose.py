"""Docker Compose parser.

Not yet implemented — this is a scaffolding placeholder. Implementation is
planned for the v0.2 milestone; see ``docs/roadmap.md``.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.parsers.base import Parser


class ComposeParser(Parser):
    """Parses ``docker-compose.yml`` files into :class:`ApplicationDefinition`."""

    format_name = "docker-compose"

    def can_parse(self, path: Path) -> bool:
        name = path.name.lower()
        return name.endswith((".yml", ".yaml")) and "compose" in name

    def parse(self, path: Path) -> ApplicationDefinition:
        raise NotImplementedError(
            "Docker Compose parsing is not yet implemented. "
            "Planned for the v0.2 milestone — see docs/roadmap.md."
        )
