from __future__ import annotations

import io

from rich.console import Console

from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.reporting.report import Reporter


def _render(result: AnalysisResult) -> str:
    buffer = io.StringIO()
    console = Console(file=buffer, force_terminal=False, width=100)
    Reporter(console=console).render(result)
    return buffer.getvalue()


def test_render_includes_confidence_percent() -> None:
    result = AnalysisResult(application_name="demo", confidence=0.87)
    output = _render(result)
    assert "87%" in output


def test_render_shows_no_findings_message_when_empty() -> None:
    result = AnalysisResult(application_name="demo", confidence=1.0)
    output = _render(result)
    assert "No findings" in output


def test_render_includes_each_finding_message() -> None:
    findings = (
        Finding(code="ports", message="Ports detected", severity=Severity.INFO),
        Finding(code="health", message="Health endpoint unknown", severity=Severity.WARNING),
    )
    result = AnalysisResult(application_name="demo", confidence=0.6, findings=findings)
    output = _render(result)
    assert "Ports detected" in output
    assert "Health endpoint unknown" in output
