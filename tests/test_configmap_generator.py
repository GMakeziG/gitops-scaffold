from __future__ import annotations

from pathlib import Path

import yaml

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.kustomize.configmap import ConfigMapGenerator
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import ApplicationDefinition, EnvVar, ServiceDefinition


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def test_no_configmap_when_no_environment() -> None:
    service = ServiceDefinition(name="web", image="nginx:1.27")
    analysis = AnalysisResult(application_name="demo", confidence=1.0)
    outcome = ConfigMapGenerator().generate(_app(service), analysis)
    assert outcome.files == ()


def test_no_configmap_when_only_secrets() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", environment=(EnvVar(name="DB_PASSWORD", value="hunter2"),)
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            Finding(
                code="secret-literal-value",
                message="m",
                severity=Severity.CRITICAL,
                service_name="web",
                field_path="environment.DB_PASSWORD",
            ),
        ),
    )
    outcome = ConfigMapGenerator().generate(_app(service), analysis)
    assert outcome.files == ()


def test_configmap_excludes_secret_and_includes_safe_values() -> None:
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(
            EnvVar(name="APP_ENV", value="production"),
            EnvVar(name="DB_PASSWORD", value="hunter2"),
        ),
    )
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            Finding(
                code="secret-literal-value",
                message="m",
                severity=Severity.CRITICAL,
                service_name="web",
                field_path="environment.DB_PASSWORD",
            ),
        ),
    )
    outcome = ConfigMapGenerator().generate(_app(service), analysis)
    assert len(outcome.files) == 1
    file = outcome.files[0]
    assert file.relative_path == Path("configmap.yaml")
    assert file.requires_review is False

    doc = yaml.safe_load(file.content)
    assert doc["kind"] == "ConfigMap"
    assert doc["data"] == {"APP_ENV": "production"}
    assert "hunter2" not in file.content


def test_configmap_quotes_ambiguous_scalars() -> None:
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(
            EnvVar(name="DEBUG", value="true"),
            EnvVar(name="PORT", value="8080"),
        ),
    )
    outcome = ConfigMapGenerator().generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["data"]["DEBUG"] == "true"
    assert isinstance(doc["data"]["DEBUG"], str)
    assert doc["data"]["PORT"] == "8080"
    assert isinstance(doc["data"]["PORT"], str)


def test_configmap_flags_interpolated_value_for_review() -> None:
    service = ServiceDefinition(
        name="web",
        image="nginx:1.27",
        environment=(EnvVar(name="LOG_LEVEL", value="${LOG_LEVEL}"),),
    )
    outcome = ConfigMapGenerator().generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    assert outcome.files[0].requires_review is True
    assert "REVIEW REQUIRED" in outcome.files[0].content
    assert len(outcome.notes) == 1
    assert outcome.notes[0].requires_review is True


def test_configmap_flags_shell_passthrough_value_for_review() -> None:
    service = ServiceDefinition(
        name="web", image="nginx:1.27", environment=(EnvVar(name="SOME_VAR", value=None),)
    )
    outcome = ConfigMapGenerator().generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    assert outcome.files[0].requires_review is True
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["data"]["SOME_VAR"] == ""


def test_configmap_resource_name_is_kebab_cased() -> None:
    service = ServiceDefinition(
        name="Web_Service", image="nginx:1.27", environment=(EnvVar(name="X", value="y"),)
    )
    outcome = ConfigMapGenerator().generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["metadata"]["name"] == "web-service-config"


def test_configmap_multi_service_uses_subdirectory_path() -> None:
    web = ServiceDefinition(name="web", image="x:1.0", environment=(EnvVar(name="X", value="y"),))
    db = ServiceDefinition(
        name="db", image="postgres:16", environment=(EnvVar(name="X", value="y"),)
    )
    outcome = ConfigMapGenerator().generate(
        _app(web, db), AnalysisResult(application_name="demo", confidence=1.0)
    )
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"web/configmap.yaml", "db/configmap.yaml"}


def test_configmap_applies_additional_labels_from_settings() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="X", value="y"),)
    )
    settings = ScaffoldSettings(additional_labels={"team": "platform"})
    outcome = ConfigMapGenerator(settings).generate(
        _app(service), AnalysisResult(application_name="demo", confidence=1.0)
    )
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["metadata"]["labels"]["team"] == "platform"
