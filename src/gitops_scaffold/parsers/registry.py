"""Dispatches a source path to whichever registered :class:`Parser` matches it.

Adding a new input format never requires touching the CLI: register the new
:class:`Parser` subclass here and :func:`detect_parser` picks it up.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.parsers.base import Parser, ParserError
from gitops_scaffold.parsers.compose import ComposeParser
from gitops_scaffold.parsers.dockerfile import DockerfileParser
from gitops_scaffold.parsers.github import GitHubRepositoryParser
from gitops_scaffold.parsers.helm import HelmParser
from gitops_scaffold.parsers.kubernetes import KubernetesParser

#: Every known input format, tried in order. Only :class:`ComposeParser` is
#: fully implemented as of v0.2 — the rest exist so the CLI never needs to
#: change when they are.
PARSERS: tuple[type[Parser], ...] = (
    ComposeParser,
    DockerfileParser,
    HelmParser,
    KubernetesParser,
    GitHubRepositoryParser,
)


def detect_parser(path: Path) -> Parser:
    """Return the first registered parser whose ``can_parse`` matches ``path``.

    Raises:
        ParserError: if no registered parser recognizes ``path``.
    """
    for parser_cls in PARSERS:
        parser = parser_cls()
        if parser.can_parse(path):
            return parser

    supported = ", ".join(parser_cls().format_name for parser_cls in PARSERS)
    raise ParserError(f"{path}: no supported parser recognized this file (supported: {supported})")
