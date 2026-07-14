"""Input format parsers.

Every parser turns some external application definition into the normalized
:class:`~gitops_scaffold.models.app.ApplicationDefinition` IR.
:class:`~gitops_scaffold.parsers.compose.ComposeParser` is the only one fully
implemented as of v0.2; the rest are scaffolding placeholders so the
architecture is future-proof — see :mod:`gitops_scaffold.parsers.registry`
and ``docs/architecture.md``.
"""

from __future__ import annotations

from gitops_scaffold.parsers.base import Parser, ParserError
from gitops_scaffold.parsers.compose import ComposeParser
from gitops_scaffold.parsers.dockerfile import DockerfileParser
from gitops_scaffold.parsers.github import GitHubRepositoryParser
from gitops_scaffold.parsers.helm import HelmParser
from gitops_scaffold.parsers.kubernetes import KubernetesParser
from gitops_scaffold.parsers.registry import PARSERS, detect_parser

__all__ = [
    "PARSERS",
    "ComposeParser",
    "DockerfileParser",
    "GitHubRepositoryParser",
    "HelmParser",
    "KubernetesParser",
    "Parser",
    "ParserError",
    "detect_parser",
]
