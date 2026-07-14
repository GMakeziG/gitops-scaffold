from __future__ import annotations

from gitops_scaffold.analyzer.scoring import compute_confidence
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition


def _app(*service_names: str) -> ApplicationDefinition:
    return ApplicationDefinition(
        name="demo",
        services=tuple(ServiceDefinition(name=name, image="x:1.0") for name in service_names),
        source_format="docker-compose",
    )


def test_no_findings_is_full_confidence() -> None:
    assert compute_confidence(_app("web"), ()) == 1.0


def test_zero_services_defaults_to_full_confidence_before_app_penalties() -> None:
    app = _app()
    findings = (Finding(code="x", message="m", severity=Severity.CRITICAL, service_name=None),)
    assert compute_confidence(app, findings) == 1.0 - 0.15


def test_single_critical_finding_costs_15_points() -> None:
    findings = (Finding(code="x", message="m", severity=Severity.CRITICAL, service_name="web"),)
    assert compute_confidence(_app("web"), findings) == 0.85


def test_single_warning_finding_costs_5_points() -> None:
    findings = (Finding(code="x", message="m", severity=Severity.WARNING, service_name="web"),)
    assert compute_confidence(_app("web"), findings) == 0.95


def test_info_findings_cost_nothing() -> None:
    findings = tuple(
        Finding(code="x", message="m", severity=Severity.INFO, service_name="web")
        for _ in range(10)
    )
    assert compute_confidence(_app("web"), findings) == 1.0


def test_per_service_score_is_clamped_at_zero() -> None:
    findings = tuple(
        Finding(code="x", message="m", severity=Severity.CRITICAL, service_name="web")
        for _ in range(10)
    )
    assert compute_confidence(_app("web"), findings) == 0.0


def test_clean_service_does_not_dilute_a_broken_one() -> None:
    # "web" is broken (2 criticals -> 0.70), "worker" is clean (1.0).
    # Averaged: (0.70 + 1.0) / 2 = 0.85 -- distinct from a flat global
    # deduction, which would instead apply the penalty once across the app.
    findings = tuple(
        Finding(code="x", message="m", severity=Severity.CRITICAL, service_name="web")
        for _ in range(2)
    )
    assert compute_confidence(_app("web", "worker"), findings) == 0.85


def test_app_level_findings_apply_after_the_service_average() -> None:
    findings = (Finding(code="x", message="m", severity=Severity.CRITICAL, service_name=None),)
    assert compute_confidence(_app("web"), findings) == 0.85


def test_confidence_never_goes_below_zero_or_above_one() -> None:
    app_level_only = (
        Finding(code="x", message="m", severity=Severity.CRITICAL, service_name=None)
        for _ in range(20)
    )
    assert compute_confidence(_app("web"), tuple(app_level_only)) == 0.0
