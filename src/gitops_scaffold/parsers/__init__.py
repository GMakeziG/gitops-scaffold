"""Input format parsers.

Every parser turns some external application definition (a Docker Compose
file today; a Helm chart, Dockerfile, or GitHub repository in future
milestones) into the normalized
:class:`~gitops_scaffold.models.app.ApplicationDefinition` IR. See
``docs/architecture.md`` for why this boundary exists.
"""

from __future__ import annotations

from gitops_scaffold.parsers.base import Parser

__all__ = ["Parser"]
