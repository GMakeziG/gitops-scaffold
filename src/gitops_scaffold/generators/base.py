"""The generator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class ManifestGenerator(ABC):
    """Base interface for producing one kind of GitOps manifest.

    Each implementation is responsible for exactly one Kubernetes (or
    Kustomize/Flux) resource kind — see the modules under
    ``generators/kustomize/`` for the concrete set (Deployment, Service,
    ConfigMap, PVC, Secret example, Ingress, Kustomization, README).
    """

    #: The resource kind this generator produces, e.g. ``"Deployment"``.
    kind: str

    @abstractmethod
    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        """Render this generator's output for ``app``.

        Must return a :class:`GenerationOutcome` with no files if this
        generator's resource kind doesn't apply to ``app`` (e.g. no Ingress
        if no HTTP port was detected), rather than emitting an empty or
        placeholder manifest — any such decision should still be recorded as
        a ``GenerationNote`` (category ``skipped``) so it's visible in
        ``generation-report.json``, not silently absent.
        """
        raise NotImplementedError
