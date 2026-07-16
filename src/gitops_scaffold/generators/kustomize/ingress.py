"""Generates the Kubernetes ``Ingress`` manifest — optional, off by default.

Only ever invoked when the CLI's ``--ingress-host`` (and the other three
required ``--ingress-*`` flags) are explicitly given; see ``cli.py``.
Scaffolding placeholder — implementation lands alongside v0.3 Component 9
(see ``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class IngressGenerator(ManifestGenerator):
    kind = "Ingress"

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        raise NotImplementedError
