from __future__ import annotations

import pytest

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.kustomize.checklist import ValidationChecklistGenerator
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
from gitops_scaffold.models.generation import GeneratedFile

ALL_GENERATORS: tuple[type[ManifestGenerator], ...] = (
    DeploymentGenerator,
    ServiceGenerator,
    ConfigMapGenerator,
    PersistentVolumeClaimGenerator,
    SecretExampleGenerator,
    IngressGenerator,
    KustomizationGenerator,
    OutputReadmeGenerator,
    ValidationChecklistGenerator,
)


def test_manifest_generator_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ManifestGenerator()  # type: ignore[abstract]


def test_concrete_generator_satisfies_the_interface(
    sample_app: ApplicationDefinition,
) -> None:
    class EmptyGenerator(ManifestGenerator):
        kind = "Empty"

        def generate(
            self, app: ApplicationDefinition, analysis: AnalysisResult
        ) -> tuple[GeneratedFile, ...]:
            return ()

    analysis = AnalysisResult(application_name=sample_app.name, confidence=1.0)
    assert EmptyGenerator().generate(sample_app, analysis) == ()


@pytest.mark.parametrize("generator_cls", ALL_GENERATORS)
def test_generator_stub_is_not_yet_implemented(
    generator_cls: type[ManifestGenerator], sample_app: ApplicationDefinition
) -> None:
    generator = generator_cls()
    assert generator.kind
    analysis = AnalysisResult(application_name=sample_app.name, confidence=1.0)
    with pytest.raises(NotImplementedError):
        generator.generate(sample_app, analysis)
