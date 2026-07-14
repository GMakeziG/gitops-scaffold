"""The analyzer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition


class Analyzer(ABC):
    """Base interface for producing an :class:`AnalysisResult` from an application.

    An analyzer must never fill in a value it isn't confident about — if a
    :class:`~gitops_scaffold.analyzer.rules.base.DetectionRule` can't determine
    something, it should emit a :class:`~gitops_scaffold.models.analysis.Finding`
    instead of guessing, so the gap is visible in both the CLI report and the
    generated manifests (as ``TODO`` / ``REVIEW REQUIRED`` markers).
    """

    @abstractmethod
    def analyze(self, app: ApplicationDefinition) -> AnalysisResult:
        raise NotImplementedError
