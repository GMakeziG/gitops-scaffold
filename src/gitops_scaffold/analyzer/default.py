"""The default, composite analyzer.

Runs every :class:`~gitops_scaffold.analyzer.rules.base.DetectionRule` over
each service, converts ``unsupported_fields`` into WARNING findings, adds its
own cross-service findings (things no single-service rule can see — host-port
collisions, "no services defined"), and computes the overall confidence score.
"""

from __future__ import annotations

from collections import defaultdict

from gitops_scaffold.analyzer.base import Analyzer
from gitops_scaffold.analyzer.rules import (
    ConfigMapDetectionRule,
    DetectionRule,
    HealthCheckDetectionRule,
    ImageTagDetectionRule,
    PersistenceDetectionRule,
    PortDetectionRule,
    RuntimeUserDetectionRule,
    SecretDetectionRule,
    SecurityRiskDetectionRule,
    VolumeDetectionRule,
    looks_like_secret,
)
from gitops_scaffold.analyzer.scoring import compute_confidence
from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition


class DefaultAnalyzer(Analyzer):
    """Runs every detection rule over each service, plus cross-service checks."""

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()
        patterns = self._settings.secret_name_patterns
        self._rules: tuple[DetectionRule, ...] = (
            PortDetectionRule(),
            SecretDetectionRule(patterns),
            ConfigMapDetectionRule(patterns),
            VolumeDetectionRule(),
            HealthCheckDetectionRule(),
            RuntimeUserDetectionRule(),
            SecurityRiskDetectionRule(),
            PersistenceDetectionRule(),
            ImageTagDetectionRule(),
        )

    def analyze(self, app: ApplicationDefinition) -> AnalysisResult:
        findings: list[Finding] = []

        for service in app.services:
            for rule in self._rules:
                findings.extend(rule.check(service))
            findings.extend(_unsupported_field_findings(service.name, service.unsupported_fields))

        findings.extend(_unsupported_field_findings(None, app.unsupported_fields))
        findings.extend(_app_level_findings(app))

        findings_tuple = tuple(findings)
        patterns = self._settings.secret_name_patterns

        return AnalysisResult(
            application_name=app.name,
            findings=findings_tuple,
            confidence=compute_confidence(app, findings_tuple),
            detected_ports=any(service.ports for service in app.services),
            detected_volumes=any(service.volumes for service in app.services),
            detected_secrets=any(
                looks_like_secret(var.name, patterns)
                for service in app.services
                for var in service.environment
            ),
            detected_health_checks=any(
                service.health_check is not None for service in app.services
            ),
            detected_runtime_user=any(service.runtime_user is not None for service in app.services),
        )


def _unsupported_field_findings(
    service_name: str | None, unsupported_fields: tuple[str, ...]
) -> tuple[Finding, ...]:
    return tuple(
        Finding(
            code="compose-unsupported-field",
            message=f"Compose field '{field}' was read but is not yet modeled by gitops-scaffold.",
            severity=Severity.WARNING,
            service_name=service_name,
            field_path=field,
            remediation="Review this field manually — it will not influence generated manifests.",
        )
        for field in unsupported_fields
    )


def _app_level_findings(app: ApplicationDefinition) -> tuple[Finding, ...]:
    findings: list[Finding] = []

    if not app.services:
        findings.append(
            Finding(
                code="app-no-services",
                message="No services are defined in this application.",
                severity=Severity.CRITICAL,
                remediation="Add at least one service to the Compose file.",
            )
        )

    host_ports: dict[int, list[str]] = defaultdict(list)
    for service in app.services:
        for port in service.ports:
            if port.host_port is not None:
                host_ports[port.host_port].append(service.name)

    for host_port, service_names in host_ports.items():
        if len(service_names) > 1:
            findings.append(
                Finding(
                    code="app-port-collision",
                    message=(
                        f"Host port {host_port} is published by multiple services: "
                        f"{', '.join(service_names)}."
                    ),
                    severity=Severity.CRITICAL,
                    remediation="Each service needs a distinct host port.",
                )
            )

    return tuple(findings)
