"""Flags non-secret environment variables suitable for a ConfigMap.

Values surfaced here are always safe to print — by definition they don't
match any pattern in :func:`~gitops_scaffold.analyzer.rules.secrets.looks_like_secret`.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.analyzer.rules.secrets import looks_like_secret
from gitops_scaffold.config.settings import DEFAULT_SECRET_NAME_PATTERNS
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class ConfigMapDetectionRule(DetectionRule):
    code = "configmap"

    def __init__(self, secret_patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS) -> None:
        self._secret_patterns = secret_patterns

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for var in service.environment:
            if looks_like_secret(var.name, self._secret_patterns):
                continue
            if var.value:
                findings.append(
                    Finding(
                        code="configmap-value-detected",
                        message=f"Service '{service.name}' config value detected: {var.name}={var.value}",
                        severity=Severity.INFO,
                        service_name=service.name,
                        field_path=f"environment.{var.name}",
                    )
                )
        return tuple(findings)
