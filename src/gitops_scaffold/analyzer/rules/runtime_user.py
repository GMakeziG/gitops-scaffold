"""Detects the runtime UID/GID a service's container runs as.

Scaffolding placeholder — see ``docs/roadmap.md`` (v0.2).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class RuntimeUserDetectionRule(DetectionRule):
    code = "runtime-user"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
