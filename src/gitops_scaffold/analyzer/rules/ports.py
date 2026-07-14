"""Flags ambiguous port bindings.

Value judgments only — parsing itself lives in ``parsers/compose.py``.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class PortDetectionRule(DetectionRule):
    code = "ports"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for index, port in enumerate(service.ports):
            if port.host_port is None:
                findings.append(
                    Finding(
                        code="ports-ambiguous-host-port",
                        message=(
                            f"Service '{service.name}' publishes container port "
                            f"{port.container_port} without an explicit host port — "
                            "Docker will assign a random ephemeral host port."
                        ),
                        severity=Severity.WARNING,
                        service_name=service.name,
                        field_path=f"ports[{index}]",
                        remediation=(
                            'Specify an explicit host port (e.g. "8080:80") for a '
                            "reproducible binding."
                        ),
                    )
                )
        return tuple(findings)
