from __future__ import annotations

import yaml

from gitops_scaffold.generators.pipeline import GenerationPipeline
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    PortMapping,
    ServiceDefinition,
    VolumeMount,
)


def _audiobookshelf_app() -> ApplicationDefinition:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="ghcr.io/advplyr/audiobookshelf:v2.35.1",
        ports=(PortMapping(container_port=80, host_port=13378),),
        environment=(EnvVar(name="TZ", value="America/New_York"),),
        volumes=(
            VolumeMount(source="./audiobooks", target="/audiobooks", mount_type="bind"),
            VolumeMount(source="./podcasts", target="/podcasts", mount_type="bind"),
            VolumeMount(source="./config", target="/config", mount_type="bind"),
            VolumeMount(source="./metadata", target="/metadata", mount_type="bind"),
        ),
        restart_policy="unless-stopped",
    )
    return ApplicationDefinition(
        name="audiobookshelf",
        services=(service,),
        source_format="docker-compose",
        source_path="tests/fixtures/compose/audiobookshelf-compose.yml",
    )


def test_audiobookshelf_end_to_end_file_set() -> None:
    app = _audiobookshelf_app()
    analysis = AnalysisResult(application_name="audiobookshelf", confidence=0.65)
    outcome = GenerationPipeline().generate(app, analysis)

    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {
        "configmap.yaml",
        "deployment.yaml",
        "service.yaml",
        "pvc.yaml",
        "kustomization.yaml",
        "README.md",
    }
    # No secret.example.yaml -- no secrets detected for this fixture.


def test_no_plaintext_secret_anywhere_in_pipeline_output() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        environment=(EnvVar(name="API_TOKEN", value="sk_live_super_secret"),),
    )
    app = ApplicationDefinition(name="demo", services=(service,), source_format="docker-compose")
    analysis = AnalysisResult(
        application_name="demo",
        confidence=0.7,
        findings=(
            Finding(
                code="secret-literal-value",
                message="m",
                severity=Severity.CRITICAL,
                service_name="web",
                field_path="environment.API_TOKEN",
            ),
        ),
    )
    outcome = GenerationPipeline().generate(app, analysis)
    for file in outcome.files:
        assert "sk_live_super_secret" not in file.content
    for note in outcome.notes:
        assert "sk_live_super_secret" not in note.message

    paths = {str(f.relative_path) for f in outcome.files}
    assert "secret.example.yaml" in paths


def test_kustomization_never_references_forbidden_files() -> None:
    app = _audiobookshelf_app()
    analysis = AnalysisResult(application_name="audiobookshelf", confidence=0.65)
    outcome = GenerationPipeline().generate(app, analysis)
    kustomization = next(f for f in outcome.files if str(f.relative_path) == "kustomization.yaml")
    doc = yaml.safe_load(kustomization.content)
    assert "secret.example.yaml" not in doc["resources"]
    assert "README.md" not in doc["resources"]
    assert "generation-report.json" not in doc["resources"]


def test_multi_service_pipeline_layout() -> None:
    web = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    db = ServiceDefinition(
        name="db",
        image="postgres:16",
        volumes=(
            VolumeMount(
                source="db-data",
                target="/var/lib/postgresql/data",
                mount_type="volume",
                is_named_volume=True,
            ),
        ),
    )
    app = ApplicationDefinition(name="demo", services=(web, db), source_format="docker-compose")
    analysis = AnalysisResult(application_name="demo", confidence=0.9)
    outcome = GenerationPipeline().generate(app, analysis)

    paths = {str(f.relative_path) for f in outcome.files}
    assert "web/deployment.yaml" in paths
    assert "web/service.yaml" in paths
    assert "db/deployment.yaml" in paths
    assert "db/pvc.yaml" in paths
    assert "kustomization.yaml" in paths
    assert "web/kustomization.yaml" in paths
    assert "db/kustomization.yaml" in paths
    assert "README.md" in paths


def test_deterministic_output_across_repeated_runs() -> None:
    app = _audiobookshelf_app()
    analysis = AnalysisResult(application_name="audiobookshelf", confidence=0.65)
    first = GenerationPipeline().generate(app, analysis)
    second = GenerationPipeline().generate(app, analysis)
    assert first == second
