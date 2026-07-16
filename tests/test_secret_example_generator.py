from __future__ import annotations

from pathlib import Path

import yaml

from gitops_scaffold.generators.kustomize.secret import SecretExampleGenerator
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition, EnvVar, ServiceDefinition


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _finding(code: str, service: str, var: str, severity: Severity = Severity.CRITICAL) -> Finding:
    return Finding(
        code=code,
        message="m",
        severity=severity,
        service_name=service,
        field_path=f"environment.{var}",
    )


def test_no_secret_example_when_no_secrets_detected() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", environment=(EnvVar(name="APP_ENV", value="prod"),)
    )
    outcome = SecretExampleGenerator().generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    assert outcome.files == ()


def test_secret_example_generated_when_secret_detected() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", environment=(EnvVar(name="API_TOKEN", value="sk_live_abc"),)
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(_finding("secret-literal-value", "web", "API_TOKEN"),),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)

    assert len(outcome.files) == 1
    file = outcome.files[0]
    assert file.relative_path == Path("secret.example.yaml")
    assert file.requires_review is True
    assert "sk_live_abc" not in file.content
    assert "***REDACTED***" not in file.content

    doc = yaml.safe_load(file.content)
    assert doc["kind"] == "Secret"
    assert doc["stringData"]["API_TOKEN"] == "CHANGE_ME"


def test_secret_example_never_includes_redaction_marker_even_if_value_is_redacted() -> None:
    # Simulates loading a report.json where analyze --output already redacted
    # the value -- the generator must never read var.value at all here.
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(EnvVar(name="API_TOKEN", value="***REDACTED***"),),
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(_finding("secret-literal-value", "web", "API_TOKEN"),),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)
    assert "***REDACTED***" not in outcome.files[0].content


def test_secret_example_marks_required_and_optional_keys_correctly() -> None:
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(
            EnvVar(name="API_TOKEN", value="literal"),
            EnvVar(name="DB_PASSWORD", value=None),
        ),
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            _finding("secret-literal-value", "web", "API_TOKEN"),
            _finding("secret-shell-passthrough", "web", "DB_PASSWORD", severity=Severity.INFO),
        ),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)
    content = outcome.files[0].content
    assert "API_TOKEN" in content
    assert "required" in content
    assert "DB_PASSWORD" in content
    assert "optional" in content

    note = next(n for n in outcome.notes if "live Secret" in n.message)
    assert "API_TOKEN" in note.message
    assert "DB_PASSWORD" in note.message
    assert "Ready" in note.message


def test_secret_example_resource_name_is_kebab_secret() -> None:
    service = ServiceDefinition(
        name="Web_Service", image="x:1.0", environment=(EnvVar(name="API_TOKEN", value="x"),)
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(_finding("secret-literal-value", "Web_Service", "API_TOKEN"),),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["metadata"]["name"] == "web-service-secret"


def test_secret_example_env_file_note_independent_of_secrets_detected() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        env_files=(".env",),
        environment=(EnvVar(name="APP_ENV", value="prod"),),
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            Finding(
                code="secret-env-file-reference",
                message="m",
                severity=Severity.INFO,
                service_name="web",
                field_path="env_file",
            ),
        ),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)
    assert outcome.files == ()
    assert any("env_file" in n.message for n in outcome.notes)


def test_secret_example_not_generated_when_service_has_no_secrets_but_has_env_file() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", env_files=(".env",))
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            Finding(
                code="secret-env-file-reference",
                message="m",
                severity=Severity.INFO,
                service_name="web",
                field_path="env_file",
            ),
        ),
    )
    outcome = SecretExampleGenerator().generate(_app(service), analysis)
    assert outcome.files == ()


def test_secret_example_multi_service_uses_subdirectory_path() -> None:
    web = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="TOKEN", value="x"),)
    )
    db = ServiceDefinition(
        name="db", image="postgres:16", environment=(EnvVar(name="PASSWORD", value="x"),)
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            _finding("secret-literal-value", "web", "TOKEN"),
            _finding("secret-literal-value", "db", "PASSWORD"),
        ),
    )
    outcome = SecretExampleGenerator().generate(_app(web, db), analysis)
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"web/secret.example.yaml", "db/secret.example.yaml"}
