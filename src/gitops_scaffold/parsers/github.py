"""GitHub repository parser.

Not yet implemented — a scaffolding placeholder mirroring
:class:`~gitops_scaffold.parsers.compose.ComposeParser`. Intended to locate
and parse a repository's Compose file or Dockerfile automatically given a
repository URL, as a convenience entrypoint. See ``docs/roadmap.md``.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.parsers.base import Parser


class GitHubRepositoryParser(Parser):
    """Locates and parses an application definition from a GitHub repository."""

    format_name = "github-repository"

    def can_parse(self, path: Path) -> bool:
        text = str(path)
        return text.startswith(("https://github.com/", "git@github.com:"))

    def parse(self, path: Path) -> ApplicationDefinition:
        raise NotImplementedError(
            "GitHub repository parsing is not yet implemented — see docs/roadmap.md."
        )
