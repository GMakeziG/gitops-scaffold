from __future__ import annotations

import pytest

from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import GenerationOutcome

# All 9 generators are implemented as of v0.3 (each has its own dedicated
# test module: test_configmap_generator.py, test_secret_example_generator.py,
# test_deployment_generator.py, test_service_generator.py,
# test_pvc_generator.py, test_kustomization_generator.py,
# test_ingress_generator.py, test_readme_generator.py). This file now only
# covers the shared ManifestGenerator ABC contract.


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
        ) -> GenerationOutcome:
            return GenerationOutcome()

    analysis = AnalysisResult(application_name=sample_app.name, confidence=1.0)
    assert EmptyGenerator().generate(sample_app, analysis) == GenerationOutcome()
