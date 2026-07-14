from __future__ import annotations

import io

from rich.console import Console

from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition, EnvVar, PortMapping, ServiceDefinition
from gitops_scaffold.reporting.report import Reporter


def _render(app: ApplicationDefinition, result: AnalysisResult) -> str:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    Reporter(console=console).render(app, result)
    return buffer.getvalue()


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def test_render_includes_confidence_percent() -> None:
    app = _app(ServiceDefinition(name="web", image="nginx:1.27"))
    result = AnalysisResult(application_name="demo", confidence=0.87)
    output = _render(app, result)
    assert "87%" in output


def test_render_shows_no_findings_message_when_empty() -> None:
    app = _app(ServiceDefinition(name="web", image="nginx:1.27"))
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(app, result)
    assert "No findings" in output


def test_render_shows_no_services_message_when_empty() -> None:
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(_app(), result)
    assert "No services detected" in output


def test_render_includes_each_finding_message() -> None:
    app = _app(ServiceDefinition(name="web", image="nginx:1.27"))
    findings = (
        Finding(code="ports", message="Ports detected", severity=Severity.INFO),
        Finding(code="health", message="Health endpoint unknown", severity=Severity.WARNING),
    )
    result = AnalysisResult(application_name="demo", confidence=0.6, findings=findings)
    output = _render(app, result)
    assert "Ports detected" in output
    assert "Health endpoint unknown" in output


def test_render_includes_service_inventory() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", ports=(PortMapping(container_port=80, host_port=8080),)
    )
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(_app(service), result)
    assert "Service: web" in output
    assert "nginx:1.27" in output
    assert "8080->80/TCP" in output


def test_render_redacts_secret_shaped_env_var_values() -> None:
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(EnvVar(name="DB_PASSWORD", value="hunter2literalsecret"),),
    )
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(_app(service), result)
    assert "hunter2literalsecret" not in output
    assert "DB_PASSWORD" in output


def test_render_does_not_redact_non_secret_env_vars() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", environment=(EnvVar(name="APP_ENV", value="production"),)
    )
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(_app(service), result)
    assert "APP_ENV=production" in output
