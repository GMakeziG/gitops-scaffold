from __future__ import annotations

import pytest

from gitops_scaffold.analyzer.base import Analyzer
from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.analyzer.rules.configmap import ConfigMapDetectionRule
from gitops_scaffold.analyzer.rules.health import HealthCheckDetectionRule
from gitops_scaffold.analyzer.rules.persistence import PersistenceDetectionRule
from gitops_scaffold.analyzer.rules.ports import PortDetectionRule
from gitops_scaffold.analyzer.rules.runtime_user import RuntimeUserDetectionRule
from gitops_scaffold.analyzer.rules.secrets import SecretDetectionRule
from gitops_scaffold.analyzer.rules.security import SecurityRiskDetectionRule
from gitops_scaffold.analyzer.rules.volumes import VolumeDetectionRule
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition

ALL_RULES: tuple[type[DetectionRule], ...] = (
    PortDetectionRule,
    SecretDetectionRule,
    ConfigMapDetectionRule,
    VolumeDetectionRule,
    HealthCheckDetectionRule,
    RuntimeUserDetectionRule,
    SecurityRiskDetectionRule,
    PersistenceDetectionRule,
)


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


@pytest.mark.parametrize("rule_cls", ALL_RULES)
def test_detection_rule_stub_is_not_yet_implemented(
    rule_cls: type[DetectionRule], sample_service: ServiceDefinition
) -> None:
    rule = rule_cls()
    assert rule.code
    with pytest.raises(NotImplementedError):
        rule.check(sample_service)
