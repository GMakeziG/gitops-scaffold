"""The output of running analyzers over an :class:`ApplicationDefinition`.

The core design constraint reflected here: the analyzer never silently
guesses. Anything it cannot determine with confidence becomes a
:class:`Finding` with an appropriate :class:`Severity`, not a default value
quietly baked into generated manifests.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    """How serious a finding is."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Finding(BaseModel):
    """A single observation produced by a detection rule.

    ``code`` is a stable, greppable identifier (e.g. ``"health-check-missing"``)
    so findings can be filtered, tested against, and documented independently
    of their human-readable ``message``. ``field_path`` is a dotted path
    relative to ``service_name`` (e.g. ``"environment.API_TOKEN"``,
    ``"ports[0]"``) pointing back to exactly what was observed, when the
    finding is about a specific field rather than the service as a whole.
    """

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    severity: Severity
    service_name: str | None = None
    field_path: str | None = None
    remediation: str | None = None


class AnalysisResult(BaseModel):
    """The full result of analyzing an application: findings plus a confidence score."""

    model_config = ConfigDict(frozen=True)

    application_name: str
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    confidence: float = Field(ge=0.0, le=1.0)
    detected_ports: bool = False
    detected_volumes: bool = False
    detected_secrets: bool = False
    detected_health_checks: bool = False
    detected_runtime_user: bool = False

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    @property
    def criticals(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.CRITICAL)

    @property
    def confidence_percent(self) -> int:
        return round(self.confidence * 100)
