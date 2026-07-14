"""Detects volume mounts and classifies them (ephemeral vs. named/bind).

Scaffolding placeholder — see ``docs/roadmap.md`` (v0.2).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class VolumeDetectionRule(DetectionRule):
    code = "volumes"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
