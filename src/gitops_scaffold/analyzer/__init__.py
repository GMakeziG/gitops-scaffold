"""Analyzers: turn an :class:`ApplicationDefinition` into an :class:`AnalysisResult`.

:class:`~gitops_scaffold.analyzer.default.DefaultAnalyzer` runs a collection
of :class:`~gitops_scaffold.analyzer.rules.base.DetectionRule` implementations
(one per concern: ports, secrets, health checks, runtime user, persistence,
security risks, image hygiene, ...) over each service, plus its own
cross-service checks, and aggregates their findings into an
:class:`AnalysisResult` with a deterministic confidence score. See
``docs/architecture.md``.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.base import Analyzer
from gitops_scaffold.analyzer.default import DefaultAnalyzer

__all__ = ["Analyzer", "DefaultAnalyzer"]
