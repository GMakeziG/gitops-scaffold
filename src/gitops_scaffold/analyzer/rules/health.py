"""Detects usable health checks and flags services with none.

Scaffolding placeholder — see ``docs/roadmap.md`` (v0.2).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class HealthCheckDetectionRule(DetectionRule):
    code = "health-check"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
