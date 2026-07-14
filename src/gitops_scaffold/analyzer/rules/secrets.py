"""Detects environment variables that look like credentials or secrets.

Anything this rule flags must never be written verbatim into a generated
Kubernetes ``Secret`` object — see ``generators/kustomize/secret.py`` and
``docs/architecture.md`` for the "never generate plaintext secrets" principle.

Scaffolding placeholder — see ``docs/roadmap.md`` (v0.2).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class SecretDetectionRule(DetectionRule):
    code = "secrets"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
