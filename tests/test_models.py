from __future__ import annotations

import pytest
from pydantic import ValidationError

from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition, PortMapping, ServiceDefinition


def test_service_definition_is_immutable(sample_service: ServiceDefinition) -> None:
    with pytest.raises(ValidationError):
        sample_service.name = "changed"  # ty: ignore[invalid-assignment]


def test_application_definition_holds_services(sample_app: ApplicationDefinition) -> None:
    assert sample_app.name == "demo"
    assert len(sample_app.services) == 1
    assert sample_app.services[0].image == "nginx:1.27"


def test_port_mapping_defaults_to_tcp() -> None:
    port = PortMapping(container_port=8080)
    assert port.protocol.value == "TCP"


def test_analysis_result_confidence_must_be_a_fraction() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult(application_name="demo", confidence=1.5)


def test_analysis_result_confidence_percent_rounds() -> None:
    result = AnalysisResult(application_name="demo", confidence=0.874)
    assert result.confidence_percent == 87


def test_analysis_result_filters_findings_by_severity() -> None:
    findings = (
        Finding(code="a", message="info finding", severity=Severity.INFO),
        Finding(code="b", message="warning finding", severity=Severity.WARNING),
        Finding(code="c", message="critical finding", severity=Severity.CRITICAL),
    )
    result = AnalysisResult(application_name="demo", confidence=0.5, findings=findings)

    assert [f.code for f in result.warnings] == ["b"]
    assert [f.code for f in result.criticals] == ["c"]
