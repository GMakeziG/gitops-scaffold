from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from gitops_scaffold.parsers.base import ParserError
from gitops_scaffold.parsers.compose import ComposeParser


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("docker-compose.yml", True),
        ("docker-compose.yaml", True),
        ("compose.yaml", True),
        ("Dockerfile", False),
        ("values.yaml", False),
    ],
)
def test_can_parse_matches_compose_filenames(filename: str, expected: bool) -> None:
    assert ComposeParser().can_parse(Path(filename)) is expected


def test_parse_audiobookshelf_fixture(compose_fixture: Callable[[str], Path]) -> None:
    app = ComposeParser().parse(compose_fixture("audiobookshelf-compose.yml"))

    assert len(app.services) == 1
    service = app.services[0]
    assert service.image == "ghcr.io/advplyr/audiobookshelf:v2.35.1"
    assert len(service.ports) == 1
    assert service.ports[0].container_port == 80
    assert service.ports[0].host_port == 13378
    assert service.runtime_user is None
    assert service.restart_policy == "unless-stopped"

    env_by_name = {var.name: var.value for var in service.environment}
    assert env_by_name == {"TZ": "America/New_York"}

    targets = {volume.target for volume in service.volumes}
    assert targets == {"/audiobooks", "/podcasts", "/config", "/metadata"}
    assert all(volume.mount_type == "bind" for volume in service.volumes)

    assert service.unsupported_fields == ("services.audiobookshelf.container_name",)


def test_parse_multi_service_fixture(compose_fixture: Callable[[str], Path]) -> None:
    app = ComposeParser().parse(compose_fixture("multi-service-compose.yml"))

    services_by_name = {service.name: service for service in app.services}
    assert set(services_by_name) == {"web", "db", "redis"}

    web = services_by_name["web"]
    assert set(web.depends_on) == {"db", "redis"}
    assert "depends_on.db.condition" in web.unsupported_fields
    assert "depends_on.redis.condition" in web.unsupported_fields

    db = services_by_name["db"]
    volume = db.volumes[0]
    assert volume.mount_type == "volume"
    assert volume.is_named_volume is True
    assert volume.source == "db-data"


def test_parse_environment_list_syntax_states(compose_fixture: Callable[[str], Path]) -> None:
    app = ComposeParser().parse(compose_fixture("environment-list-syntax-compose.yml"))
    env_by_name = {var.name: var.value for var in app.services[0].environment}

    assert env_by_name["APP_ENV"] == "production"
    assert env_by_name["DEBUG"] == ""
    assert env_by_name["SHELL_PASSTHROUGH"] is None


def test_parse_ports_short_syntax_edge_cases(compose_fixture: Callable[[str], Path]) -> None:
    service = ComposeParser().parse(compose_fixture("ports-short-syntax-compose.yml")).services[0]
    ports = {(p.container_port, p.host_port, p.protocol.value) for p in service.ports}

    assert (80, 8080, "TCP") in ports
    assert (90, 9090, "TCP") in ports
    assert (53, 53, "UDP") in ports
    assert (3000, None, "TCP") in ports

    assert any("host_ip=127.0.0.1" in field for field in service.unsupported_fields)


def test_parse_ports_long_syntax(compose_fixture: Callable[[str], Path]) -> None:
    service = ComposeParser().parse(compose_fixture("ports-long-syntax-compose.yml")).services[0]

    assert len(service.ports) == 1
    assert service.ports[0].container_port == 80
    assert service.ports[0].host_port == 8080
    assert any("9000-9010" in field for field in service.unsupported_fields)


def test_parse_named_volumes_with_read_only(compose_fixture: Callable[[str], Path]) -> None:
    service = ComposeParser().parse(compose_fixture("named-volumes-compose.yml")).services[0]
    by_target = {v.target: v for v in service.volumes}

    assert by_target["/var/lib/app"].is_named_volume is True
    assert by_target["/var/lib/app"].read_only is False
    assert by_target["/var/cache/app"].is_named_volume is True
    assert by_target["/var/cache/app"].read_only is True


def test_parse_bind_mounts(compose_fixture: Callable[[str], Path]) -> None:
    service = ComposeParser().parse(compose_fixture("bind-mounts-compose.yml")).services[0]
    by_target = {v.target: v for v in service.volumes}

    assert by_target["/data"].mount_type == "bind"
    assert by_target["/data"].read_only is False
    assert by_target["/etc/localtime"].mount_type == "bind"
    assert by_target["/etc/localtime"].read_only is True


def test_parse_healthcheck_full_timing_and_disabled_variant(
    compose_fixture: Callable[[str], Path],
) -> None:
    app = ComposeParser().parse(compose_fixture("healthcheck-compose.yml"))
    services_by_name = {service.name: service for service in app.services}

    web_health = services_by_name["web"].health_check
    assert web_health is not None
    assert web_health.interval_seconds == 30
    assert web_health.timeout_seconds == 10
    assert web_health.start_period_seconds == 60
    assert web_health.retries == 3
    assert web_health.disabled is False

    worker_health = services_by_name["worker"].health_check
    assert worker_health is not None
    assert worker_health.disabled is True


def test_parse_secrets_fixture_classification_inputs(
    compose_fixture: Callable[[str], Path],
) -> None:
    service = ComposeParser().parse(compose_fixture("secrets-compose.yml")).services[0]
    env_by_name = {var.name: var.value for var in service.environment}

    assert env_by_name["API_TOKEN"] == "sk_live_hardcoded_literal_value_12345"
    assert env_by_name["CLIENT_SECRET"] == "${CLIENT_SECRET}"
    assert env_by_name["ACCESS_KEY"] == ""
    assert env_by_name["PRIVATE_KEY"] is None
    assert env_by_name["APP_ENV"] == "production"
    assert service.env_files == (".env",)


@pytest.mark.parametrize(
    "filename",
    [
        "yaml-syntax-error-compose.yml",
        "non-mapping-root-compose.yml",
        "missing-services-key-compose.yml",
        "service-not-a-mapping-compose.yml",
    ],
)
def test_parse_rejects_malformed_input(
    filename: str, compose_fixture: Callable[[str], Path]
) -> None:
    path = compose_fixture(f"malformed/{filename}")
    with pytest.raises(ParserError):
        ComposeParser().parse(path)


def test_parse_null_services_is_not_malformed(compose_fixture: Callable[[str], Path]) -> None:
    app = ComposeParser().parse(compose_fixture("malformed/null-services-compose.yml"))
    assert app.services == ()


def test_parse_advanced_fields(compose_fixture: Callable[[str], Path]) -> None:
    app = ComposeParser().parse(compose_fixture("advanced-fields-compose.yml"))
    services_by_name = {service.name: service for service in app.services}

    web = services_by_name["app"]
    assert web.command == ("bundle", "exec", "thin", "-p", "3000")
    assert web.entrypoint == ("/entrypoint.sh", "--flag")
    assert web.env_files == (".env",)
    assert web.labels == {"com.example.team": "platform", "com.example.tier": "backend"}
    assert set(web.network_aliases) == {"app-internal", "app.local"}
    assert "services.app.networks.default.ipv4_address" in web.unsupported_fields
    assert "services.app.deploy.replicas" in web.unsupported_fields
    assert "services.app.deploy.resources.limits.pids" in web.unsupported_fields
    assert web.resources is not None
    assert web.resources.cpu_request == "0.25"
    assert web.resources.memory_request == "256M"
    assert web.resources.cpu_limit == "1.0"
    assert web.resources.memory_limit == "512M"

    worker = services_by_name["worker"]
    assert worker.command == ("python", "worker.py")
    assert worker.labels == {"com.example.team": "platform"}
    by_target = {v.target: v for v in worker.volumes}
    assert by_target["/tmp/scratch"].mount_type == "tmpfs"
    assert by_target["/tmp/scratch"].source is None
    assert by_target["/data"].mount_type == "volume"
    assert by_target["/data"].source is None
    assert by_target["/data"].is_named_volume is False


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("ports", "not-a-list"),
        ("volumes", "not-a-list"),
        ("healthcheck", "not-a-mapping"),
        ("depends_on", 123),
        ("networks", "not-a-mapping-or-list"),
    ],
)
def test_parse_rejects_wrong_shaped_fields(field: str, bad_value: object, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", field: bad_value}}})
    )
    with pytest.raises(ParserError):
        ComposeParser().parse(compose_file)


@pytest.mark.parametrize(
    "port_spec",
    [
        "8080:80/xyz",  # unrecognized protocol
        "8080-8090:80",  # host port range
        "a:b:c:d",  # too many colons
        "abc:def",  # non-numeric
    ],
)
def test_parse_ports_degrades_gracefully_on_unrecognized_specs(
    port_spec: str, tmp_path: Path
) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "ports": [port_spec]}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.ports == ()
    assert len(service.unsupported_fields) == 1


def test_parse_empty_file_is_rejected_as_no_services(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("")
    with pytest.raises(ParserError, match="no 'services' section"):
        ComposeParser().parse(compose_file)


def test_parse_rejects_non_mapping_services_value(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: not-a-mapping\n")
    with pytest.raises(ParserError, match="must be a mapping"):
        ComposeParser().parse(compose_file)


def test_can_parse_content_sniffs_unconventionally_named_files(tmp_path: Path) -> None:
    path = tmp_path / "my-app.yml"
    path.write_text("services:\n  app:\n    image: x:1.0\n")
    assert ComposeParser().can_parse(path) is True


def test_can_parse_returns_false_for_a_directory(tmp_path: Path) -> None:
    directory = tmp_path / "some-dir.yml"
    directory.mkdir()
    assert ComposeParser().can_parse(directory) is False


def test_parse_raises_clear_error_for_a_directory(tmp_path: Path) -> None:
    directory = tmp_path / "docker-compose.yml"
    directory.mkdir()
    with pytest.raises(ParserError, match="Could not read"):
        ComposeParser().parse(directory)


@pytest.mark.parametrize(
    ("raw_user", "uid", "gid", "raw"),
    [
        ("1000:1000", 1000, 1000, "1000:1000"),
        ("appuser", None, None, "appuser"),
        ("1000", 1000, None, "1000"),
        ("1000:appgroup", 1000, None, "1000:appgroup"),
    ],
)
def test_parse_user_forms(
    raw_user: str, uid: int | None, gid: int | None, raw: str, tmp_path: Path
) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "user": raw_user}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.runtime_user is not None
    assert service.runtime_user.uid == uid
    assert service.runtime_user.gid == gid
    assert service.runtime_user.raw == raw


def test_parse_command_rejects_unsupported_type(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "command": 123}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.command is None


def test_parse_environment_stringifies_boolean_values(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "environment": {"DEBUG": True}}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.environment[0].value == "true"


def test_parse_env_file_ignores_unsupported_type(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "env_file": 123}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.env_files == ()


def test_parse_ports_bracketed_ipv6_host() -> None:
    from gitops_scaffold.parsers.compose import _parse_port_spec

    mapping, note = _parse_port_spec(0, "[::1]:3000:3000")
    assert mapping is not None
    assert mapping.container_port == 3000
    assert mapping.host_port == 3000
    assert note is not None
    assert "host_ip=::1" in note


@pytest.mark.parametrize(
    "entry",
    [
        {"published": 8080},  # missing target
        {"target": "not-a-number"},
        None,
        ["nested", "list"],
    ],
)
def test_parse_ports_long_syntax_degrades_gracefully(entry: object, tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "ports": [entry]}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.ports == ()
    assert len(service.unsupported_fields) == 1


def test_parse_short_volume_anonymous_with_read_only_suffix() -> None:
    from gitops_scaffold.parsers.compose import _parse_short_volume

    mount, note = _parse_short_volume("/data:ro", frozenset())
    assert mount.source is None
    assert mount.target == "/data"
    assert mount.read_only is True
    assert note is None


def test_parse_short_volume_flags_undeclared_named_volume() -> None:
    from gitops_scaffold.parsers.compose import _parse_short_volume

    mount, note = _parse_short_volume("cache:/var/cache", frozenset())
    assert mount.is_named_volume is True
    assert note == "volumes references undeclared volume 'cache'"


def test_parse_long_volume_missing_target_and_undeclared_name() -> None:
    from gitops_scaffold.parsers.compose import _parse_long_volume

    mount, note = _parse_long_volume(0, {"published": 1}, frozenset())
    assert mount is None
    assert note is not None
    assert "missing 'target'" in note

    mount, note = _parse_long_volume(
        0, {"type": "volume", "source": "cache", "target": "/x"}, frozenset()
    )
    assert mount is not None
    assert note == "volumes[0] references undeclared volume 'cache'"


def test_parse_volumes_entry_unrecognized_type(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "volumes": [123]}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.volumes == ()
    assert len(service.unsupported_fields) == 1


def test_parse_healthcheck_rejects_unparseable_duration(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "app": {
                        "image": "x:1.0",
                        "healthcheck": {"test": "curl localhost", "interval": "not-a-duration"},
                    }
                }
            }
        )
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.health_check is not None
    assert service.health_check.interval_seconds is None
    assert any("healthcheck.interval" in field for field in service.unsupported_fields)


def test_parse_depends_on_short_list_form(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump(
            {
                "services": {
                    "web": {"image": "x:1.0", "depends_on": ["db"]},
                    "db": {"image": "postgres:16"},
                }
            }
        )
    )
    web = next(s for s in ComposeParser().parse(compose_file).services if s.name == "web")
    assert web.depends_on == ("db",)


def test_parse_deploy_rejects_wrong_shapes(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "deploy": "not-a-mapping"}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.resources is None
    assert "services.app.deploy" in service.unsupported_fields


def test_parse_deploy_resources_wrong_shape(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "deploy": {"resources": "oops"}}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.resources is None
    assert "services.app.deploy.resources" in service.unsupported_fields


def test_parse_networks_ignores_non_mapping_network_entries(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "networks": {"default": None}}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.network_aliases == ()


def test_parse_labels_ignores_unsupported_type(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(
        yaml.safe_dump({"services": {"app": {"image": "x:1.0", "labels": 123}}})
    )
    service = ComposeParser().parse(compose_file).services[0]
    assert service.labels == {}
