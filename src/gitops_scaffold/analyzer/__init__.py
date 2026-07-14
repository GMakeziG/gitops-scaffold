"""Analyzers: turn an :class:`ApplicationDefinition` into an :class:`AnalysisResult`.

An analyzer runs a collection of :class:`~gitops_scaffold.analyzer.rules.base.DetectionRule`
implementations (one per concern: ports, secrets, health checks, runtime user,
persistence, security risks, ...) over each service and aggregates their
findings, plus an overall confidence score. See ``docs/architecture.md``.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.base import Analyzer

__all__ = ["Analyzer"]
