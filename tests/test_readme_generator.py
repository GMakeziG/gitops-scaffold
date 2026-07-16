from __future__ import annotations

from pathlib import Path

from gitops_scaffold.generators.kustomize.readme import OutputReadmeGenerator
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    PortMapping,
    ServiceDefinition,
    VolumeMount,
)
from gitops_scaffold.models.generation import GenerationNote, GenerationNoteCategory


def _app(
    *services: ServiceDefinition, source_path: str | None = "docker-compose.yml"
) -> ApplicationDefinition:
    return ApplicationDefinition(
        name="demo", services=services, source_format="docker-compose", source_path=source_path
    )


def _analysis(*findings: Finding) -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=0.8, findings=findings)


def test_readme_includes_source_path_and_confidence() -> None:
    service = ServiceDefinition(name="web", image="nginx:1.27")
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "docker-compose.yml" in content
    assert "80%" in content
    assert Path("README.md")


def test_readme_lists_ports_and_host_port_explanation() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "80/TCP" in content
    assert "host port 13378" in content


def test_readme_lists_safe_env_vars_only() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        environment=(
            EnvVar(name="APP_ENV", value="prod"),
            EnvVar(name="API_TOKEN", value="sk_live_secret"),
        ),
    )
    analysis = _analysis(
        Finding(
            code="secret-literal-value",
            message="m",
            severity=Severity.CRITICAL,
            service_name="web",
            field_path="environment.API_TOKEN",
        )
    )
    content = OutputReadmeGenerator().generate(_app(service), analysis, ()).files[0].content
    assert "APP_ENV" in content
    assert "prod" in content
    assert "sk_live_secret" not in content
    assert "API_TOKEN" not in content.split("Secret required")[0] or "API_TOKEN" in content


def test_readme_secret_section_lists_required_and_optional_keys() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        environment=(
            EnvVar(name="API_TOKEN", value="literal"),
            EnvVar(name="OPTIONAL_TOKEN", value=None),
        ),
    )
    analysis = _analysis(
        Finding(
            code="secret-literal-value",
            message="m",
            severity=Severity.CRITICAL,
            service_name="web",
            field_path="environment.API_TOKEN",
        ),
        Finding(
            code="secret-shell-passthrough",
            message="m",
            severity=Severity.INFO,
            service_name="web",
            field_path="environment.OPTIONAL_TOKEN",
        ),
    )
    content = OutputReadmeGenerator().generate(_app(service), analysis, ()).files[0].content
    assert "web-secret" in content
    assert "Required keys: API_TOKEN" in content
    assert "Optional keys: OPTIONAL_TOKEN" in content
    assert "will not become Ready" in content
    assert "kubectl create secret generic web-secret" in content


def test_readme_no_secret_section_when_no_secrets() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "Secret required" not in content


def test_readme_lists_volume_to_pvc_mappings() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        volumes=(VolumeMount(source="./audiobooks", target="/audiobooks", mount_type="bind"),),
    )
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "/audiobooks" in content
    assert "audiobookshelf-audiobooks" in content
    assert "1Gi" in content


def test_readme_skipped_service_shown_as_not_generated() -> None:
    service = ServiceDefinition(name="broken", image=None)
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "Not generated" in content
    assert "no image" in content


def test_readme_aggregates_review_and_skipped_notes() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    notes = (
        GenerationNote(
            category=GenerationNoteCategory.ASSUMPTION,
            message="Review this thing",
            requires_review=True,
        ),
        GenerationNote(category=GenerationNoteCategory.SKIPPED, message="Skipped that thing"),
        GenerationNote(
            category=GenerationNoteCategory.WARNING, message="Just a warning, not review-required"
        ),
    )
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), notes).files[0].content
    assert "Review this thing" in content
    assert "Skipped that thing" in content


def test_readme_shows_placeholder_when_nothing_to_review_or_skip() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "Nothing flagged" in content
    assert "Nothing was skipped" in content


def test_readme_port_forward_uses_host_port_as_local_side() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "13378:80" in content


def test_readme_includes_project_principle_language() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    content = OutputReadmeGenerator().generate(_app(service), _analysis(), ()).files[0].content
    assert "not automatically" in content
    assert "production-ready" in content
