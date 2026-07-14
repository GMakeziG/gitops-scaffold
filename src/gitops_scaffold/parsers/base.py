"""The parser interface every input format implementation must satisfy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from gitops_scaffold.models.app import ApplicationDefinition


class Parser(ABC):
    """Base interface for turning an input format into an :class:`ApplicationDefinition`.

    Implementations must not silently guess at values they cannot determine —
    leave them ``None`` (or empty) and let the analyzer surface a finding
    instead. See ``docs/architecture.md`` for the full rationale.
    """

    #: A short, stable identifier for this format, e.g. ``"docker-compose"``.
    format_name: str

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Return whether this parser is a plausible match for ``path``.

        Used by the CLI to auto-detect the input format when one isn't
        specified explicitly.
        """
        raise NotImplementedError

    @abstractmethod
    def parse(self, path: Path) -> ApplicationDefinition:
        """Parse ``path`` into a normalized :class:`ApplicationDefinition`.

        Raises:
            ParserError: if ``path`` cannot be parsed as this format.
        """
        raise NotImplementedError


class ParserError(Exception):
    """Raised when a parser cannot make sense of its input."""
