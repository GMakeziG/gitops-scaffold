from __future__ import annotations

from pathlib import Path

import yaml

from gitops_scaffold.generators.kustomize.kustomization import KustomizationGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    PortMapping,
    ServiceDefinition,
    VolumeMount,
)


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _analysis() -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=1.0)


def test_single_service_flat_kustomization_lists_only_applicable_files() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80),),
        environment=(EnvVar(name="TZ", value="UTC"),),
        volumes=(VolumeMount(source="./data", target="/data", mount_type="bind"),),
    )
    outcome = KustomizationGenerator().generate(_app(service), _analysis())
    assert len(outcome.files) == 1
    assert outcome.files[0].relative_path == Path("kustomization.yaml")
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["resources"] == ["configmap.yaml", "pvc.yaml", "deployment.yaml", "service.yaml"]
    assert doc["namespace"] == "default"


def test_never_lists_forbidden_files() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="API_TOKEN", value="x"),)
    )
    from gitops_scaffold.models.analysis import Finding, Severity

    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
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
    outcome = KustomizationGenerator().generate(_app(service), analysis)
    content = outcome.files[0].content
    assert "secret.example.yaml" not in content
    assert "README.md" not in content
    assert "generation-report.json" not in content


def test_no_service_or_configmap_when_not_applicable() -> None:
    service = ServiceDefinition(name="worker", image="x:1.0")
    outcome = KustomizationGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["resources"] == ["deployment.yaml"]


def test_multi_service_root_references_subdirectories() -> None:
    web = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    db = ServiceDefinition(name="db", image="postgres:16")
    outcome = KustomizationGenerator().generate(_app(web, db), _analysis())

    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"kustomization.yaml", "web/kustomization.yaml", "db/kustomization.yaml"}

    root = next(f for f in outcome.files if str(f.relative_path) == "kustomization.yaml")
    root_doc = yaml.safe_load(root.content)
    assert set(root_doc["resources"]) == {"web", "db"}
    assert root_doc["namespace"] == "default"

    web_doc = yaml.safe_load(
        next(f for f in outcome.files if str(f.relative_path) == "web/kustomization.yaml").content
    )
    assert web_doc["resources"] == ["deployment.yaml", "service.yaml"]
    assert "namespace" not in web_doc


def test_multi_service_root_includes_shared_pvc() -> None:
    web = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="shared-data", target="/data", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    backup = ServiceDefinition(
        name="backup",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="shared-data", target="/backup", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    outcome = KustomizationGenerator().generate(_app(web, backup), _analysis())
    root = next(f for f in outcome.files if str(f.relative_path) == "kustomization.yaml")
    root_doc = yaml.safe_load(root.content)
    assert "pvc.yaml" in root_doc["resources"]
    assert set(root_doc["resources"]) == {"web", "backup", "pvc.yaml"}


def test_service_with_no_image_excluded_from_kustomization() -> None:
    web = ServiceDefinition(name="web", image="x:1.0")
    broken = ServiceDefinition(name="broken", image=None)
    outcome = KustomizationGenerator().generate(_app(web, broken), _analysis())
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"kustomization.yaml", "web/kustomization.yaml"}
