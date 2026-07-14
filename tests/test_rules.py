from __future__ import annotations

from typing import Any

from gitops_scaffold.analyzer.rules.configmap import ConfigMapDetectionRule
from gitops_scaffold.analyzer.rules.health import HealthCheckDetectionRule
from gitops_scaffold.analyzer.rules.image import ImageTagDetectionRule
from gitops_scaffold.analyzer.rules.persistence import PersistenceDetectionRule
from gitops_scaffold.analyzer.rules.ports import PortDetectionRule
from gitops_scaffold.analyzer.rules.runtime_user import RuntimeUserDetectionRule
from gitops_scaffold.analyzer.rules.secrets import SecretDetectionRule, looks_like_secret
from gitops_scaffold.analyzer.rules.security import SecurityRiskDetectionRule
from gitops_scaffold.analyzer.rules.volumes import VolumeDetectionRule
from gitops_scaffold.models.analysis import Severity
from gitops_scaffold.models.app import (
    EnvVar,
    HealthCheck,
    PortMapping,
    RuntimeUser,
    ServiceDefinition,
    VolumeMount,
)


def _service(**overrides: Any) -> ServiceDefinition:
    defaults: dict[str, Any] = {"name": "svc", "image": "myorg/app:1.0.0"}
    defaults.update(overrides)
    return ServiceDefinition(**defaults)


# --- ports -------------------------------------------------------------


def test_ports_rule_flags_missing_host_port() -> None:
    service = _service(ports=(PortMapping(container_port=80),))
    findings = PortDetectionRule().check(service)
    assert [f.code for f in findings] == ["ports-ambiguous-host-port"]
    assert findings[0].severity is Severity.WARNING


def test_ports_rule_silent_when_host_port_explicit() -> None:
    service = _service(ports=(PortMapping(container_port=80, host_port=8080),))
    assert PortDetectionRule().check(service) == ()


# --- secrets -------------------------------------------------------------


def test_looks_like_secret_matches_case_insensitively() -> None:
    assert looks_like_secret("db_password")
    assert looks_like_secret("API_KEY")
    assert not looks_like_secret("APP_ENV")


def test_secrets_rule_classifies_literal_as_critical() -> None:
    service = _service(environment=(EnvVar(name="API_TOKEN", value="sk_live_abc123"),))
    findings = SecretDetectionRule().check(service)
    assert findings[0].code == "secret-literal-value"
    assert findings[0].severity is Severity.CRITICAL
    assert "sk_live_abc123" not in findings[0].message


def test_secrets_rule_classifies_empty_as_warning() -> None:
    service = _service(environment=(EnvVar(name="API_TOKEN", value=""),))
    findings = SecretDetectionRule().check(service)
    assert findings[0].code == "secret-empty"
    assert findings[0].severity is Severity.WARNING


def test_secrets_rule_classifies_interpolation_as_info() -> None:
    service = _service(environment=(EnvVar(name="API_TOKEN", value="${API_TOKEN}"),))
    findings = SecretDetectionRule().check(service)
    assert findings[0].code == "secret-interpolated"
    assert findings[0].severity is Severity.INFO


def test_secrets_rule_classifies_shell_passthrough_as_info() -> None:
    service = _service(environment=(EnvVar(name="API_TOKEN", value=None),))
    findings = SecretDetectionRule().check(service)
    assert findings[0].code == "secret-shell-passthrough"
    assert findings[0].severity is Severity.INFO


def test_secrets_rule_ignores_non_secret_names() -> None:
    service = _service(environment=(EnvVar(name="APP_ENV", value="production"),))
    assert SecretDetectionRule().check(service) == ()


def test_secrets_rule_flags_env_file_reference() -> None:
    service = _service(env_files=(".env",))
    findings = SecretDetectionRule().check(service)
    assert [f.code for f in findings] == ["secret-env-file-reference"]
    assert findings[0].severity is Severity.INFO


# --- configmap -------------------------------------------------------------


def test_configmap_rule_flags_non_secret_literal_values() -> None:
    service = _service(environment=(EnvVar(name="APP_ENV", value="production"),))
    findings = ConfigMapDetectionRule().check(service)
    assert findings[0].code == "configmap-value-detected"
    assert "production" in findings[0].message


def test_configmap_rule_ignores_secret_shaped_names() -> None:
    service = _service(environment=(EnvVar(name="DB_PASSWORD", value="hunter2"),))
    assert ConfigMapDetectionRule().check(service) == ()


# --- volumes -------------------------------------------------------------


def test_volumes_rule_flags_bind_mount() -> None:
    service = _service(volumes=(VolumeMount(source="./data", target="/data", mount_type="bind"),))
    findings = VolumeDetectionRule().check(service)
    assert findings[0].code == "volume-bind-mount"
    assert findings[0].severity is Severity.WARNING


def test_volumes_rule_flags_anonymous_volume() -> None:
    service = _service(volumes=(VolumeMount(source=None, target="/data", mount_type="volume"),))
    findings = VolumeDetectionRule().check(service)
    assert findings[0].code == "volume-anonymous"
    assert findings[0].severity is Severity.WARNING


def test_volumes_rule_flags_named_volume_as_info() -> None:
    service = _service(
        volumes=(
            VolumeMount(source="data", target="/data", mount_type="volume", is_named_volume=True),
        )
    )
    findings = VolumeDetectionRule().check(service)
    assert findings[0].code == "volume-named"
    assert findings[0].severity is Severity.INFO


def test_volumes_rule_flags_tmpfs_as_info() -> None:
    service = _service(volumes=(VolumeMount(source=None, target="/tmp", mount_type="tmpfs"),))
    findings = VolumeDetectionRule().check(service)
    assert findings[0].code == "volume-tmpfs"
    assert findings[0].severity is Severity.INFO


# --- health --------------------------------------------------------------


def test_health_rule_flags_missing_healthcheck() -> None:
    findings = HealthCheckDetectionRule().check(_service())
    assert findings[0].code == "health-check-missing"
    assert findings[0].severity is Severity.WARNING


def test_health_rule_flags_disabled_as_info() -> None:
    service = _service(health_check=HealthCheck(disabled=True))
    findings = HealthCheckDetectionRule().check(service)
    assert findings[0].code == "health-check-disabled"
    assert findings[0].severity is Severity.INFO


def test_health_rule_flags_present_as_info() -> None:
    service = _service(health_check=HealthCheck(test="curl -f http://localhost"))
    findings = HealthCheckDetectionRule().check(service)
    assert findings[0].code == "health-check-present"
    assert findings[0].severity is Severity.INFO


# --- runtime_user ----------------------------------------------------------


def test_runtime_user_rule_flags_unspecified() -> None:
    findings = RuntimeUserDetectionRule().check(_service())
    assert findings[0].code == "runtime-user-unspecified"
    assert findings[0].severity is Severity.WARNING


def test_runtime_user_rule_flags_root_as_critical() -> None:
    service = _service(runtime_user=RuntimeUser(uid=0, gid=0, raw="0:0"))
    findings = RuntimeUserDetectionRule().check(service)
    assert findings[0].code == "runtime-user-root"
    assert findings[0].severity is Severity.CRITICAL


def test_runtime_user_rule_flags_unresolved_name_as_warning() -> None:
    service = _service(runtime_user=RuntimeUser(uid=None, gid=None, raw="appuser"))
    findings = RuntimeUserDetectionRule().check(service)
    assert findings[0].code == "runtime-user-unresolved"
    assert findings[0].severity is Severity.WARNING


def test_runtime_user_rule_flags_resolved_nonzero_as_info() -> None:
    service = _service(runtime_user=RuntimeUser(uid=1000, gid=1000, raw="1000:1000"))
    findings = RuntimeUserDetectionRule().check(service)
    assert findings[0].code == "runtime-user-detected"
    assert findings[0].severity is Severity.INFO


# --- security --------------------------------------------------------------


def test_security_rule_flags_privileged_as_critical() -> None:
    findings = SecurityRiskDetectionRule().check(_service(privileged=True))
    assert findings[0].code == "security-privileged"
    assert findings[0].severity is Severity.CRITICAL


def test_security_rule_flags_host_network_as_critical() -> None:
    findings = SecurityRiskDetectionRule().check(_service(network_mode="host"))
    assert findings[0].code == "security-host-network"
    assert findings[0].severity is Severity.CRITICAL


def test_security_rule_does_not_flag_other_network_modes() -> None:
    findings = SecurityRiskDetectionRule().check(_service(network_mode="service:db"))
    assert findings == ()


def test_security_rule_silent_by_default() -> None:
    assert SecurityRiskDetectionRule().check(_service()) == ()


# --- persistence -------------------------------------------------------------


def test_persistence_rule_flags_named_volume_as_warning() -> None:
    service = _service(
        volumes=(
            VolumeMount(source="data", target="/data", mount_type="volume", is_named_volume=True),
        )
    )
    findings = PersistenceDetectionRule().check(service)
    assert findings[0].code == "persistence-storage-size-unknown"
    assert findings[0].severity is Severity.WARNING


def test_persistence_rule_ignores_read_only_named_volume() -> None:
    service = _service(
        volumes=(
            VolumeMount(
                source="data",
                target="/data",
                mount_type="volume",
                is_named_volume=True,
                read_only=True,
            ),
        )
    )
    assert PersistenceDetectionRule().check(service) == ()


def test_persistence_rule_ignores_bind_mounts() -> None:
    service = _service(volumes=(VolumeMount(source="./data", target="/data", mount_type="bind"),))
    assert PersistenceDetectionRule().check(service) == ()


def test_persistence_rule_ignores_tmpfs() -> None:
    service = _service(volumes=(VolumeMount(source=None, target="/tmp", mount_type="tmpfs"),))
    assert PersistenceDetectionRule().check(service) == ()


# --- image -------------------------------------------------------------


def test_image_rule_flags_missing_image_as_critical() -> None:
    findings = ImageTagDetectionRule().check(_service(image=None))
    assert findings[0].code == "image-missing"
    assert findings[0].severity is Severity.CRITICAL


def test_image_rule_flags_missing_tag_as_warning() -> None:
    findings = ImageTagDetectionRule().check(_service(image="nginx"))
    assert findings[0].code == "image-tag-missing"
    assert findings[0].severity is Severity.WARNING


def test_image_rule_flags_latest_as_warning() -> None:
    findings = ImageTagDetectionRule().check(_service(image="nginx:latest"))
    assert findings[0].code == "image-tag-latest"
    assert findings[0].severity is Severity.WARNING


def test_image_rule_flags_pinned_tag_as_info() -> None:
    findings = ImageTagDetectionRule().check(
        _service(image="ghcr.io/advplyr/audiobookshelf:v2.35.1")
    )
    assert findings[0].code == "image-tag-pinned"
    assert findings[0].severity is Severity.INFO


def test_image_rule_flags_digest_pin_as_info() -> None:
    findings = ImageTagDetectionRule().check(_service(image="nginx@sha256:" + "a" * 64))
    assert findings[0].code == "image-pinned-digest"
    assert findings[0].severity is Severity.INFO


def test_image_rule_handles_registry_port_without_tag() -> None:
    findings = ImageTagDetectionRule().check(_service(image="localhost:5000/app"))
    assert findings[0].code == "image-tag-missing"


def test_image_rule_handles_registry_port_with_tag() -> None:
    findings = ImageTagDetectionRule().check(_service(image="localhost:5000/app:2.0"))
    assert findings[0].code == "image-tag-pinned"
