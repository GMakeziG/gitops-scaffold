"""Generates ``secret.example.yaml`` placeholders — never real ``Secret`` objects.

This generator must never write a real Kubernetes ``Secret`` containing
plaintext values. It only ever produces an example/placeholder file (with
empty or ``CHANGEME`` values) documenting what keys the application expects,
so operators can populate real secrets through their own secret manager
(SealedSecrets, External Secrets Operator, SOPS, etc.).

Renders ``templates/secret.example.yaml.j2``. Scaffolding placeholder — see
``docs/roadmap.md`` (v0.2/v0.3).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GeneratedFile


class SecretExampleGenerator(ManifestGenerator):
    kind = "SecretExample"

    def generate(
        self, app: ApplicationDefinition, analysis: AnalysisResult
    ) -> tuple[GeneratedFile, ...]:
        raise NotImplementedError
