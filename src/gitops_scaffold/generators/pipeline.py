"""Orchestrates every generator into one :class:`GenerationOutcome` for an application.

This is the single place manifest generation actually happens, regardless of
whether the caller's input was a fresh Compose parse or a cached
``AnalysisReport`` — see ``cli.py``'s input resolution, which converges on
one ``(application, analysis)`` pair before calling
:meth:`GenerationPipeline.generate` exactly once.
"""

from __future__ import annotations

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.ingress_config import IngressConfig
from gitops_scaffold.generators.kustomize.configmap import ConfigMapGenerator
from gitops_scaffold.generators.kustomize.deployment import DeploymentGenerator
from gitops_scaffold.generators.kustomize.ingress import IngressGenerator
from gitops_scaffold.generators.kustomize.kustomization import KustomizationGenerator
from gitops_scaffold.generators.kustomize.pvc import PersistentVolumeClaimGenerator
from gitops_scaffold.generators.kustomize.readme import OutputReadmeGenerator
from gitops_scaffold.generators.kustomize.secret import SecretExampleGenerator
from gitops_scaffold.generators.kustomize.service import ServiceGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome


class GenerationPipeline:
    """Runs every manifest generator over an application and assembles one outcome."""

    def __init__(
        self,
        settings: ScaffoldSettings | None = None,
        ingress_config: IngressConfig | None = None,
    ) -> None:
        self._settings = settings or ScaffoldSettings()
        self._generators: tuple[ManifestGenerator, ...] = (
            ConfigMapGenerator(self._settings),
            SecretExampleGenerator(self._settings),
            DeploymentGenerator(self._settings),
            ServiceGenerator(self._settings),
            PersistentVolumeClaimGenerator(self._settings),
            IngressGenerator(self._settings, ingress_config),
            KustomizationGenerator(self._settings, ingress_config),
        )
        self._readme_generator = OutputReadmeGenerator(self._settings)

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files = []
        notes = []
        for generator in self._generators:
            outcome = generator.generate(app, analysis)
            files.extend(outcome.files)
            notes.extend(outcome.notes)

        # README is generated last since it's the one piece that needs the
        # aggregated notes from everything else -- see readme.py's docstring
        # for why it doesn't implement the standard ManifestGenerator interface.
        readme_outcome = self._readme_generator.generate(app, analysis, tuple(notes))
        files.extend(readme_outcome.files)
        notes.extend(readme_outcome.notes)

        return GenerationOutcome(files=tuple(files), notes=tuple(notes))
