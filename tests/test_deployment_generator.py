from __future__ import annotations

import yaml

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.kustomize.deployment import DeploymentGenerator
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    HealthCheck,
    PortMapping,
    ResourceRequirements,
    RuntimeUser,
    ServiceDefinition,
    VolumeMount,
)


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _analysis(*findings: Finding) -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=1.0, findings=findings)


def _generate(
    service: ServiceDefinition, *findings: Finding, settings: ScaffoldSettings | None = None
):
    outcome = DeploymentGenerator(settings).generate(_app(service), _analysis(*findings))
    return outcome


# --- image handling -------------------------------------------------------------


def test_skips_service_entirely_when_image_missing() -> None:
    service = ServiceDefinition(name="web", image=None)
    outcome = _generate(service)
    assert outcome.files == ()
    assert outcome.notes[0].category.value == "skipped"
    assert outcome.notes[0].requires_review is True


def test_flags_image_review_when_tag_missing_or_latest() -> None:
    service = ServiceDefinition(name="web", image="nginx:latest")
    finding = Finding(
        code="image-tag-latest",
        message="pinned to latest",
        severity=Severity.WARNING,
        service_name="web",
    )
    outcome = _generate(service, finding)
    assert outcome.files[0].requires_review is True
    assert "REVIEW REQUIRED" in outcome.files[0].content


def test_no_image_review_when_tag_pinned() -> None:
    service = ServiceDefinition(name="web", image="nginx:1.27")
    finding = Finding(
        code="image-tag-pinned", message="pinned", severity=Severity.INFO, service_name="web"
    )
    outcome = _generate(service, finding)
    # requires_review may still be True for other reasons (no user, no health
    # check) -- specifically check the image line has no review comment.
    assert "REVIEW REQUIRED" not in outcome.files[0].content.split("image:")[0].split("\n")[-2]


# --- command/entrypoint mapping -------------------------------------------------------------


def test_neither_command_nor_entrypoint_set() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert "command" not in container
    assert "args" not in container


def test_only_command_set_maps_to_args() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", command=("bundle", "exec", "thin"))
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert "command" not in container
    assert container["args"] == ["bundle", "exec", "thin"]


def test_only_entrypoint_set_maps_to_command() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", entrypoint=("/entrypoint.sh",))
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["/entrypoint.sh"]
    assert "args" not in container


def test_both_command_and_entrypoint_set() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", entrypoint=("/entrypoint.sh",), command=("--flag",)
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert container["command"] == ["/entrypoint.sh"]
    assert container["args"] == ["--flag"]


# --- configmap / secret env -------------------------------------------------------------


def test_envfrom_configmap_only_when_non_secret_vars_exist() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="APP_ENV", value="prod"),)
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert container["envFrom"] == [{"configMapRef": {"name": "web-config"}}]


def test_no_envfrom_when_no_non_secret_vars() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="DB_PASSWORD", value="x"),)
    )
    finding = Finding(
        code="secret-literal-value",
        message="m",
        severity=Severity.CRITICAL,
        service_name="web",
        field_path="environment.DB_PASSWORD",
    )
    outcome = _generate(service, finding)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert "envFrom" not in container


def test_secret_env_uses_secret_key_ref_required_by_default() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="API_TOKEN", value="literal"),)
    )
    finding = Finding(
        code="secret-literal-value",
        message="m",
        severity=Severity.CRITICAL,
        service_name="web",
        field_path="environment.API_TOKEN",
    )
    outcome = _generate(service, finding)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    entry = container["env"][0]
    assert entry["name"] == "API_TOKEN"
    assert entry["valueFrom"]["secretKeyRef"]["name"] == "web-secret"
    assert entry["valueFrom"]["secretKeyRef"]["key"] == "API_TOKEN"
    assert "optional" not in entry["valueFrom"]["secretKeyRef"]
    assert outcome.files[0].requires_review is True


def test_secret_env_shell_passthrough_is_optional() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", environment=(EnvVar(name="API_TOKEN", value=None),)
    )
    finding = Finding(
        code="secret-shell-passthrough",
        message="m",
        severity=Severity.INFO,
        service_name="web",
        field_path="environment.API_TOKEN",
    )
    outcome = _generate(service, finding)
    doc = yaml.safe_load(outcome.files[0].content)
    entry = doc["spec"]["template"]["spec"]["containers"][0]["env"][0]
    assert entry["valueFrom"]["secretKeyRef"]["optional"] is True


def test_never_renders_plaintext_secret_value() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        environment=(EnvVar(name="API_TOKEN", value="sk_live_super_secret"),),
    )
    finding = Finding(
        code="secret-literal-value",
        message="m",
        severity=Severity.CRITICAL,
        service_name="web",
        field_path="environment.API_TOKEN",
    )
    outcome = _generate(service, finding)
    assert "sk_live_super_secret" not in outcome.files[0].content


# --- ports -------------------------------------------------------------


def test_named_container_ports() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", ports=(PortMapping(container_port=80, host_port=13378),)
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    port = doc["spec"]["template"]["spec"]["containers"][0]["ports"][0]
    assert port["containerPort"] == 80
    assert port["name"]
    assert "13378" not in outcome.files[0].content


# --- volumes -------------------------------------------------------------


def test_volume_mounts_and_pod_volumes_reference_matching_pvc() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        volumes=(VolumeMount(source="./audiobooks", target="/audiobooks", mount_type="bind"),),
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    mount = container["volumeMounts"][0]
    volume = doc["spec"]["template"]["spec"]["volumes"][0]
    assert mount["mountPath"] == "/audiobooks"
    assert mount["name"] == volume["name"]
    assert volume["persistentVolumeClaim"]["claimName"] == mount["name"]


def test_excluded_bind_mount_gets_no_volume_mount() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="/var/run/docker.sock", target="/var/run/docker.sock", mount_type="bind"
            ),
        ),
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert "volumeMounts" not in container
    assert "volumes" not in doc["spec"]["template"]["spec"]


# --- probes -------------------------------------------------------------


def test_readiness_probe_generated_by_default_no_liveness() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        health_check=HealthCheck(test="curl -f http://localhost", interval_seconds=30, retries=3),
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    container = doc["spec"]["template"]["spec"]["containers"][0]
    assert "readinessProbe" in container
    assert "livenessProbe" not in container


def test_liveness_probe_only_when_enabled_in_settings() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", health_check=HealthCheck(test="curl -f http://localhost")
    )
    outcome = _generate(service, settings=ScaffoldSettings(enable_liveness_probe=True))
    doc = yaml.safe_load(outcome.files[0].content)
    assert "livenessProbe" in doc["spec"]["template"]["spec"]["containers"][0]


def test_startup_probe_generated_when_start_period_present() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        health_check=HealthCheck(
            test="curl -f http://localhost", interval_seconds=10, start_period_seconds=60
        ),
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    probe = doc["spec"]["template"]["spec"]["containers"][0]["startupProbe"]
    assert probe["periodSeconds"] == 10
    assert probe["failureThreshold"] == 6


def test_no_startup_probe_without_start_period() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", health_check=HealthCheck(test="curl -f http://localhost")
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert "startupProbe" not in doc["spec"]["template"]["spec"]["containers"][0]


def test_missing_healthcheck_produces_todo_and_review() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    assert "TODO" in outcome.files[0].content
    assert outcome.files[0].requires_review is True
    assert any(n.requires_review and "health check" in n.message for n in outcome.notes)


def test_disabled_healthcheck_is_informational_not_review_required() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", health_check=HealthCheck(disabled=True))
    outcome = _generate(service)
    assert "TODO" not in outcome.files[0].content
    disabled_notes = [n for n in outcome.notes if "disables its health check" in n.message]
    assert len(disabled_notes) == 1
    assert disabled_notes[0].requires_review is False


# --- resources -------------------------------------------------------------


def test_resources_pass_through_when_present() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        resources=ResourceRequirements(
            cpu_request="0.5", memory_request="256Mi", cpu_limit="1", memory_limit="512Mi"
        ),
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    resources = doc["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"] == {"cpu": "0.5", "memory": "256Mi"}
    assert resources["limits"] == {"cpu": "1", "memory": "512Mi"}


def test_no_resources_block_when_nothing_configured() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert "resources" not in doc["spec"]["template"]["spec"]["containers"][0]


def test_configured_defaults_applied_only_when_compose_silent() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    settings = ScaffoldSettings(default_cpu_request="0.1", default_memory_limit="128Mi")
    outcome = _generate(service, settings=settings)
    doc = yaml.safe_load(outcome.files[0].content)
    resources = doc["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert resources["requests"] == {"cpu": "0.1"}
    assert resources["limits"] == {"memory": "128Mi"}


def test_non_k8s_shaped_memory_flagged_for_review() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", resources=ResourceRequirements(memory_limit="1GB-ish")
    )
    outcome = _generate(service)
    assert outcome.files[0].requires_review is True
    assert any("doesn't look like a Kubernetes quantity" in n.message for n in outcome.notes)


# --- security context -------------------------------------------------------------


def test_no_security_context_when_user_unspecified() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert "securityContext" not in doc["spec"]["template"]["spec"]
    assert outcome.files[0].requires_review is True


def test_no_security_context_when_user_unresolved_by_name() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", runtime_user=RuntimeUser(raw="appuser"))
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert "securityContext" not in doc["spec"]["template"]["spec"]


def test_security_context_when_uid_resolved() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", runtime_user=RuntimeUser(uid=1000, gid=1000, raw="1000:1000")
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    security_context = doc["spec"]["template"]["spec"]["securityContext"]
    assert security_context["runAsUser"] == 1000
    assert security_context["runAsGroup"] == 1000
    assert security_context["runAsNonRoot"] is True


def test_security_context_root_user_sets_run_as_non_root_false() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", runtime_user=RuntimeUser(uid=0, gid=0, raw="0:0")
    )
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["template"]["spec"]["securityContext"]["runAsNonRoot"] is False


# --- restart policy -------------------------------------------------------------


def test_restart_policy_never_rendered_but_documented() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", restart_policy="unless-stopped")
    outcome = _generate(service)
    assert "unless-stopped" not in outcome.files[0].content
    assert any("restart policy" in n.message for n in outcome.notes)


def test_no_restart_note_when_unset() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    assert not any("restart policy" in n.message for n in outcome.notes)


# --- labels / naming / layout -------------------------------------------------------------


def test_selector_matches_pod_template_labels() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    selector = doc["spec"]["selector"]["matchLabels"]
    pod_labels = doc["spec"]["template"]["metadata"]["labels"]
    assert selector.items() <= pod_labels.items()


def test_multi_service_uses_subdirectory_path() -> None:
    web = ServiceDefinition(name="web", image="x:1.0")
    db = ServiceDefinition(name="db", image="postgres:16")
    outcome = DeploymentGenerator().generate(_app(web, db), _analysis())
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"web/deployment.yaml", "db/deployment.yaml"}


def test_replicas_is_always_one() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = _generate(service)
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["replicas"] == 1
