"""Detects non-secret environment variables suitable for a ConfigMap.

Scaffolding placeholder — see ``docs/roadmap.md`` (v0.2).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class ConfigMapDetectionRule(DetectionRule):
    code = "configmap"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
