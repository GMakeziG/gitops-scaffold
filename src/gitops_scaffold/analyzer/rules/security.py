"""Flags container isolation risks: privileged mode and host networking.

Both are treated as CRITICAL, same tier — each is a total opt-out of a
container isolation boundary with no safe Kubernetes equivalent.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class SecurityRiskDetectionRule(DetectionRule):
    code = "security-risk"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []

        if service.privileged:
            findings.append(
                Finding(
                    code="security-privileged",
                    message=(
                        f"Service '{service.name}' runs in privileged mode — full host "
                        "device/kernel access."
                    ),
                    severity=Severity.CRITICAL,
                    service_name=service.name,
                    field_path="privileged",
                    remediation="Remove privileged mode; grant only the specific capabilities needed.",
                )
            )

        if service.network_mode == "host":
            findings.append(
                Finding(
                    code="security-host-network",
                    message=(
                        f"Service '{service.name}' uses host networking — bypasses network "
                        "namespace isolation."
                    ),
                    severity=Severity.CRITICAL,
                    service_name=service.name,
                    field_path="network_mode",
                    remediation="Use a regular Service/Ingress instead of host networking.",
                )
            )

        return tuple(findings)
