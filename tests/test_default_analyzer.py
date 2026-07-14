from __future__ import annotations

from gitops_scaffold.analyzer.default import DefaultAnalyzer
from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    HealthCheck,
    PortMapping,
    RuntimeUser,
    ServiceDefinition,
)


def test_no_services_produces_critical_finding_and_low_confidence() -> None:
    app = ApplicationDefinition(name="empty", services=(), source_format="docker-compose")
    result = DefaultAnalyzer().analyze(app)

    assert any(f.code == "app-no-services" for f in result.findings)
    assert result.confidence == 1.0 - 0.15


def test_port_collision_across_services_is_flagged_critical() -> None:
    web = ServiceDefinition(
        name="web", image="a:1.0", ports=(PortMapping(container_port=80, host_port=8080),)
    )
    admin = ServiceDefinition(
        name="admin", image="b:1.0", ports=(PortMapping(container_port=90, host_port=8080),)
    )
    app = ApplicationDefinition(name="demo", services=(web, admin), source_format="docker-compose")
    result = DefaultAnalyzer().analyze(app)

    collisions = [f for f in result.findings if f.code == "app-port-collision"]
    assert len(collisions) == 1
    assert collisions[0].service_name is None
    assert collisions[0].severity.value == "critical"


def test_no_collision_when_host_ports_differ() -> None:
    web = ServiceDefinition(
        name="web", image="a:1.0", ports=(PortMapping(container_port=80, host_port=8080),)
    )
    admin = ServiceDefinition(
        name="admin", image="b:1.0", ports=(PortMapping(container_port=90, host_port=9090),)
    )
    app = ApplicationDefinition(name="demo", services=(web, admin), source_format="docker-compose")
    result = DefaultAnalyzer().analyze(app)

    assert not [f for f in result.findings if f.code == "app-port-collision"]


def test_unsupported_fields_become_warning_findings() -> None:
    service = ServiceDefinition(
        name="web", image="a:1.0", unsupported_fields=("services.web.container_name",)
    )
    app = ApplicationDefinition(
        name="demo",
        services=(service,),
        source_format="docker-compose",
        unsupported_fields=("secrets",),
    )
    result = DefaultAnalyzer().analyze(app)

    service_level = [
        f
        for f in result.findings
        if f.code == "compose-unsupported-field" and f.service_name == "web"
    ]
    app_level = [
        f
        for f in result.findings
        if f.code == "compose-unsupported-field" and f.service_name is None
    ]
    assert service_level[0].field_path == "services.web.container_name"
    assert app_level[0].field_path == "secrets"


def test_detected_flags_reflect_the_application() -> None:
    service = ServiceDefinition(
        name="web",
        image="a:1.0",
        ports=(PortMapping(container_port=80, host_port=8080),),
        environment=(EnvVar(name="DB_PASSWORD", value="hunter2"),),
        health_check=HealthCheck(test="curl localhost"),
        runtime_user=RuntimeUser(uid=1000, gid=1000, raw="1000:1000"),
    )
    app = ApplicationDefinition(name="demo", services=(service,), source_format="docker-compose")
    result = DefaultAnalyzer().analyze(app)

    assert result.detected_ports is True
    assert result.detected_volumes is False
    assert result.detected_secrets is True
    assert result.detected_health_checks is True
    assert result.detected_runtime_user is True


def test_custom_secret_patterns_from_settings_are_honored() -> None:
    service = ServiceDefinition(
        name="web", image="a:1.0", environment=(EnvVar(name="MY_CUSTOM_CRED", value="x"),)
    )
    app = ApplicationDefinition(name="demo", services=(service,), source_format="docker-compose")

    default_result = DefaultAnalyzer().analyze(app)
    assert not any(f.code.startswith("secret-") for f in default_result.findings)

    settings = ScaffoldSettings(secret_name_patterns=("MY_CUSTOM_CRED",))
    custom_result = DefaultAnalyzer(settings).analyze(app)
    assert any(f.code == "secret-literal-value" for f in custom_result.findings)
