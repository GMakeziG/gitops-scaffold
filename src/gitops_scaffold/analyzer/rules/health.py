"""Flags missing, disabled, or present health checks."""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class HealthCheckDetectionRule(DetectionRule):
    code = "health-check"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        health = service.health_check

        if health is None:
            return (
                Finding(
                    code="health-check-missing",
                    message=f"Service '{service.name}' declares no health check.",
                    severity=Severity.WARNING,
                    service_name=service.name,
                    field_path="healthcheck",
                    remediation=(
                        "Add a healthcheck so readiness/liveness probes can be generated "
                        "automatically."
                    ),
                ),
            )

        if health.disabled:
            return (
                Finding(
                    code="health-check-disabled",
                    message=f"Service '{service.name}' explicitly disables its health check.",
                    severity=Severity.INFO,
                    service_name=service.name,
                    field_path="healthcheck",
                ),
            )

        return (
            Finding(
                code="health-check-present",
                message=f"Service '{service.name}' has a health check configured.",
                severity=Severity.INFO,
                service_name=service.name,
                field_path="healthcheck",
            ),
        )
