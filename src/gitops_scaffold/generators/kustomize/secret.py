"""Generates ``secret.example.yaml`` placeholders — never real ``Secret`` objects.

This generator must never write a real Kubernetes ``Secret`` containing
plaintext values. It only ever produces an example/placeholder file (with
``CHANGE_ME`` values) documenting what keys the application expects, so
operators can populate real secrets through their own secret manager
(SealedSecrets, External Secrets Operator, SOPS, etc.).

Scaffolding placeholder — implementation lands in v0.3 Component 4 (see
``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class SecretExampleGenerator(ManifestGenerator):
    kind = "SecretExample"

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        raise NotImplementedError
