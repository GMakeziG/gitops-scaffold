"""Deterministic, explainable confidence scoring.

Each service starts at 1.0 (100%); a CRITICAL finding attributed to it costs
``CRITICAL_PENALTY``, a WARNING costs ``WARNING_PENALTY``, INFO costs nothing
— clamped to ``[0.0, 1.0]``. The application-level score is the average
across all services (an app with none skips straight to a base of 1.0), then
the same per-finding penalties are applied for app-level findings
(``Finding.service_name is None`` — cross-service checks like port
collisions or "no services defined"), and the result is clamped again. Pure
function of its inputs — fully deterministic. See ``docs/compose-support.md``.
"""

from __future__ import annotations

from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition

CRITICAL_PENALTY = 0.15
WARNING_PENALTY = 0.05

_PENALTY_BY_SEVERITY: dict[Severity, float] = {
    Severity.CRITICAL: CRITICAL_PENALTY,
    Severity.WARNING: WARNING_PENALTY,
    Severity.INFO: 0.0,
}


def _score(findings: tuple[Finding, ...]) -> float:
    penalty = sum(_PENALTY_BY_SEVERITY[finding.severity] for finding in findings)
    return max(0.0, 1.0 - penalty)


def compute_confidence(app: ApplicationDefinition, findings: tuple[Finding, ...]) -> float:
    """Compute a deterministic confidence score for ``app`` given ``findings``."""
    if app.services:
        service_scores = [
            _score(tuple(f for f in findings if f.service_name == service.name))
            for service in app.services
        ]
        base = sum(service_scores) / len(service_scores)
    else:
        base = 1.0

    app_level_findings = tuple(f for f in findings if f.service_name is None)
    app_level_penalty = sum(_PENALTY_BY_SEVERITY[f.severity] for f in app_level_findings)

    return max(0.0, min(1.0, base - app_level_penalty))
