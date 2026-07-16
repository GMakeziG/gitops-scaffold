from __future__ import annotations

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.labels import pod_selector_labels, standard_labels
from gitops_scaffold.generators.ports import plan_ports
from gitops_scaffold.generators.secret_classification import (
    has_env_file_reference,
    is_optional,
    secret_classifications,
)
from gitops_scaffold.generators.volumes import plan_volumes
from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    PortMapping,
    Protocol,
    ServiceDefinition,
    VolumeMount,
)
from gitops_scaffold.utils.naming import find_collisions, k8s_resource_name, kebab_case

# --- naming -------------------------------------------------------------


def test_kebab_case_lowercases_and_hyphenates() -> None:
    assert kebab_case("My_Service Name") == "my-service-name"


def test_kebab_case_strips_invalid_characters() -> None:
    # Dots aren't valid in a DNS-1123 label either, so they're stripped too.
    assert kebab_case("app@v1.2!!") == "app-v1-2"


def test_kebab_case_never_returns_empty() -> None:
    assert kebab_case("###") == "unnamed"


def test_k8s_resource_name_joins_parts() -> None:
    assert k8s_resource_name("web", "/var/lib/data") == "web-var-lib-data"


def test_k8s_resource_name_truncates_deterministically() -> None:
    long_name = "x" * 300
    truncated = k8s_resource_name(long_name, max_length=253)
    assert len(truncated) <= 253
    # Same input always produces the same truncated name.
    assert truncated == k8s_resource_name(long_name, max_length=253)


def test_find_collisions_detects_duplicates() -> None:
    collisions = find_collisions(["a", "b", "a", "c", "b"])
    assert collisions == {"a": [0, 2], "b": [1, 4]}


def test_find_collisions_empty_when_all_unique() -> None:
    assert find_collisions(["a", "b", "c"]) == {}


# --- labels -------------------------------------------------------------


def _app(service: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=(service,), source_format="docker-compose")


def test_pod_selector_labels_excludes_additional_labels() -> None:
    service = ServiceDefinition(name="web", image="nginx:1.27")
    labels = pod_selector_labels(service, _app(service))
    assert labels == {
        "app.kubernetes.io/name": "web",
        "app.kubernetes.io/part-of": "demo",
    }


def test_standard_labels_is_a_superset_of_selector_labels() -> None:
    service = ServiceDefinition(name="web", image="nginx:1.27")
    settings = ScaffoldSettings(additional_labels={"team": "platform"})
    selector = pod_selector_labels(service, _app(service))
    full = standard_labels(service, _app(service), settings)
    assert selector.items() <= full.items()
    assert full["app.kubernetes.io/managed-by"] == "gitops-scaffold"
    assert full["team"] == "platform"


# --- ports -------------------------------------------------------------


def test_plan_ports_names_by_protocol_and_port() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    plan = plan_ports(service, ScaffoldSettings())
    assert plan.ports[0].name == "tcp-80"
    assert plan.ports[0].container_port == 80
    assert plan.notes == ()


def test_plan_ports_dedupes_identical_names() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        ports=(
            PortMapping(container_port=80, name="http"),
            PortMapping(container_port=8080, name="http"),
        ),
    )
    plan = plan_ports(service, ScaffoldSettings())
    names = [p.name for p in plan.ports]
    assert names == ["http", "http-2"]


def test_plan_ports_applies_override_for_single_port_service() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    settings = ScaffoldSettings(port_overrides={"audiobookshelf": 3005})
    plan = plan_ports(service, settings)
    assert plan.ports[0].container_port == 3005
    assert plan.notes[0].category.value == "assumption"


def test_plan_ports_ignores_override_for_multi_port_service() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        ports=(PortMapping(container_port=80), PortMapping(container_port=443)),
    )
    settings = ScaffoldSettings(port_overrides={"web": 3005})
    plan = plan_ports(service, settings)
    assert [p.container_port for p in plan.ports] == [80, 443]
    assert plan.notes[0].category.value == "skipped"
    assert plan.notes[0].requires_review is True


def test_plan_ports_preserves_udp_protocol() -> None:
    service = ServiceDefinition(
        name="dns", image="x:1.0", ports=(PortMapping(container_port=53, protocol=Protocol.UDP),)
    )
    plan = plan_ports(service, ScaffoldSettings())
    assert plan.ports[0].protocol == "UDP"
    assert plan.ports[0].name == "udp-53"


def test_plan_ports_never_touches_host_port() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", ports=(PortMapping(container_port=80, host_port=13378),)
    )
    plan = plan_ports(service, ScaffoldSettings())
    assert plan.ports[0].container_port == 80
    # PlannedPort has no host_port field at all -- structurally impossible
    # to leak it into a manifest.
    assert not hasattr(plan.ports[0], "host_port")


# --- secret classification -------------------------------------------------------------


def _finding(code: str, service: str, var: str) -> Finding:
    return Finding(
        code=code,
        message="m",
        severity=Severity.INFO,
        service_name=service,
        field_path=f"environment.{var}",
    )


def test_secret_classifications_derives_from_findings_only() -> None:
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(
            _finding("secret-literal-value", "web", "API_TOKEN"),
            _finding("secret-shell-passthrough", "web", "DB_PASSWORD"),
            Finding(
                code="configmap-value-detected",
                message="m",
                severity=Severity.INFO,
                service_name="web",
            ),
        ),
    )
    classifications = secret_classifications("web", analysis)
    assert classifications == {
        "API_TOKEN": "secret-literal-value",
        "DB_PASSWORD": "secret-shell-passthrough",
    }


def test_secret_classifications_excludes_env_file_reference() -> None:
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
    assert secret_classifications("web", analysis) == {}
    assert has_env_file_reference("web", analysis) is True


def test_secret_classifications_scoped_per_service() -> None:
    analysis = AnalysisResult(
        application_name="demo",
        confidence=1.0,
        findings=(_finding("secret-literal-value", "db", "PASSWORD"),),
    )
    assert secret_classifications("web", analysis) == {}
    assert secret_classifications("db", analysis) == {"PASSWORD": "secret-literal-value"}


def test_is_optional_only_true_for_shell_passthrough() -> None:
    assert is_optional("secret-shell-passthrough") is True
    assert is_optional("secret-literal-value") is False
    assert is_optional("secret-empty") is False
    assert is_optional("secret-interpolated") is False


# --- volumes -------------------------------------------------------------


def test_plan_volumes_skips_tmpfs() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(VolumeMount(source=None, target="/tmp/x", mount_type="tmpfs"),),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert plan.service_pvcs["web"] == ()
    assert plan.service_mounts["web"] == ()
    assert any("ephemeral" in n.message for n in plan.notes)


def test_plan_volumes_skips_docker_socket() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="/var/run/docker.sock", target="/var/run/docker.sock", mount_type="bind"
            ),
        ),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert plan.service_pvcs["web"] == ()
    assert plan.service_mounts["web"] == ()


def test_plan_volumes_skips_known_single_file_mounts() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="/etc/localtime", target="/etc/localtime", read_only=True, mount_type="bind"
            ),
        ),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert plan.service_pvcs["web"] == ()


def test_plan_volumes_flags_ambiguous_file_mounts_without_converting() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="./nginx.conf",
                target="/etc/nginx/nginx.conf",
                read_only=True,
                mount_type="bind",
            ),
        ),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert plan.service_pvcs["web"] == ()
    note = next(n for n in plan.notes if "nginx.conf" in n.message)
    assert note.requires_review is True


def test_plan_volumes_converts_data_bind_mount_to_pvc() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        volumes=(VolumeMount(source="./audiobooks", target="/audiobooks", mount_type="bind"),),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert len(plan.service_pvcs["audiobookshelf"]) == 1
    pvc = plan.service_pvcs["audiobookshelf"][0]
    assert pvc.target == "/audiobooks"
    assert pvc.shared is False
    assert plan.service_mounts["audiobookshelf"] == (plan.service_mounts["audiobookshelf"][0],)


def test_plan_volumes_converts_anonymous_volume() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(VolumeMount(source=None, target="/data", mount_type="volume"),),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    assert len(plan.service_pvcs["web"]) == 1
    assert plan.service_pvcs["web"][0].source_description == "anonymous volume"


def test_plan_volumes_dedupes_shared_named_volume_across_services() -> None:
    web = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="db-data", target="/data", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    backup = ServiceDefinition(
        name="backup",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="db-data", target="/backup-src", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    app = ApplicationDefinition(name="demo", services=(web, backup), source_format="docker-compose")

    plan = plan_volumes(app, ScaffoldSettings())

    assert len(plan.shared_pvcs) == 1
    shared = plan.shared_pvcs[0]
    assert shared.shared is True
    assert set(shared.service_names) == {"web", "backup"}
    assert plan.service_pvcs["web"] == ()
    assert plan.service_pvcs["backup"] == ()
    assert plan.service_mounts["web"][0].pvc_name == shared.name
    assert plan.service_mounts["backup"][0].pvc_name == shared.name
    # Each service keeps its own mount target even though the PVC is shared.
    assert plan.service_mounts["web"][0].target == "/data"
    assert plan.service_mounts["backup"][0].target == "/backup-src"


def test_plan_volumes_single_service_named_volume_is_not_shared() -> None:
    service = ServiceDefinition(
        name="db",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="db-data", target="/data", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    plan = plan_volumes(_app(service), ScaffoldSettings())
    # A named volume used by only one service belongs in that service's own
    # bucket, not the shared/root one -- "shared" only applies when 2+
    # services actually mount the same Compose volume.
    assert plan.shared_pvcs == ()
    assert len(plan.service_pvcs["db"]) == 1
    assert plan.service_pvcs["db"][0].shared is False
