from __future__ import annotations

import pytest

from gitops_scaffold.analyzer.base import Analyzer
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition


def test_analyzer_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        Analyzer()  # type: ignore[abstract]


def test_concrete_analyzer_satisfies_the_interface(sample_app: ApplicationDefinition) -> None:
    class AlwaysConfidentAnalyzer(Analyzer):
        def analyze(self, app: ApplicationDefinition) -> AnalysisResult:
            return AnalysisResult(application_name=app.name, confidence=1.0)

    result = AlwaysConfidentAnalyzer().analyze(sample_app)
    assert result.application_name == "demo"
    assert result.confidence == 1.0
