"""Docker Compose parser (modern Compose Specification).

This module only ever answers "what does this file structurally declare?" —
value judgments ("no healthcheck is a problem", "`:latest` is bad practice")
never happen here; they belong to ``analyzer/rules/*.py``. Anything this
parser reads but doesn't model gets recorded (as a dotted path) in
``unsupported_fields`` rather than silently dropped. See
``docs/compose-support.md`` for the full supported/unsupported field table
and the exact malformed-input policy.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    HealthCheck,
    PortMapping,
    Protocol,
    ResourceRequirements,
    RuntimeUser,
    ServiceDefinition,
    VolumeMount,
)
from gitops_scaffold.parsers.base import Parser, ParserError
from gitops_scaffold.utils.duration import parse_duration_to_seconds

#: Per-service fields this parser actively extracts. Everything else (aside
#: from ``x-*`` extensions) becomes an ``unsupported_fields`` entry.
_KNOWN_SERVICE_FIELDS = frozenset(
    {
        "image",
        "command",
        "entrypoint",
        "environment",
        "env_file",
        "ports",
        "volumes",
        "user",
        "healthcheck",
        "depends_on",
        "restart",
        "deploy",
        "labels",
        "networks",
        "network_mode",
        "privileged",
    }
)

#: Top-level fields recognized (and, for ``version``, intentionally ignored
#: per Compose-spec convention rather than reported as unsupported).
_KNOWN_TOP_LEVEL_FIELDS = frozenset({"version", "name", "services", "volumes", "networks"})

_KNOWN_HEALTHCHECK_FIELDS = frozenset(
    {"test", "interval", "timeout", "start_period", "retries", "disable"}
)

_PORT_RANGE_PATTERN = re.compile(r"^\d+-\d+$")


class ComposeParser(Parser):
    """Parses ``docker-compose.yml`` files into :class:`ApplicationDefinition`."""

    format_name = "docker-compose"

    def can_parse(self, path: Path) -> bool:
        if path.suffix.lower() not in {".yml", ".yaml"}:
            return False
        if "compose" in path.name.lower():
            return True
        # Fall back to content-sniffing so unconventionally-named files
        # (not literally "docker-compose.yml") are still recognized.
        try:
            document = yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError):
            return False
        return isinstance(document, dict) and "services" in document

    def parse(self, path: Path) -> ApplicationDefinition:
        document = _load_yaml(path)

        if "services" not in document:
            raise ParserError(f"{path}: no 'services' section found — is this a Compose file?")

        raw_services = document.get("services") or {}
        if not isinstance(raw_services, dict):
            raise ParserError(f"{path}: 'services' must be a mapping of service name to definition")

        volume_names = _known_volume_names(document.get("volumes"))

        services: list[ServiceDefinition] = []
        for service_name, raw_service in raw_services.items():
            if not isinstance(raw_service, dict):
                raise ParserError(
                    f"{path}: service '{service_name}' must be a mapping, "
                    f"got {type(raw_service).__name__}"
                )
            try:
                services.append(_parse_service(service_name, raw_service, volume_names))
            except ParserError:
                raise
            except ValidationError as exc:
                raise ParserError(f"{path}: service '{service_name}': {exc}") from exc

        unsupported_fields = tuple(
            key
            for key in document
            if key not in _KNOWN_TOP_LEVEL_FIELDS and not key.startswith("x-")
        )

        app_name = document.get("name") or path.stem

        try:
            return ApplicationDefinition(
                name=str(app_name),
                services=tuple(services),
                source_format=self.format_name,
                source_path=str(path),
                unsupported_fields=unsupported_fields,
            )
        except ValidationError as exc:
            raise ParserError(f"{path}: {exc}") from exc


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text()
    except OSError as exc:
        raise ParserError(f"Could not read {path}: {exc}") from exc

    try:
        document = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ParserError(f"{path} is not valid YAML: {exc}") from exc

    if document is None:
        document = {}

    if not isinstance(document, dict):
        raise ParserError(
            f"{path}: the top level of a Compose file must be a mapping, "
            f"got {type(document).__name__}"
        )

    return document


def _known_volume_names(raw: Any) -> frozenset[str]:
    if isinstance(raw, dict):
        return frozenset(str(name) for name in raw)
    return frozenset()


def _parse_service(
    name: str, raw: dict[str, Any], volume_names: frozenset[str]
) -> ServiceDefinition:
    unsupported: list[str] = []

    image = raw.get("image")
    command = _parse_command_like(raw.get("command"))
    entrypoint = _parse_command_like(raw.get("entrypoint"))
    environment = _parse_environment(raw.get("environment"))
    env_files = _as_tuple_of_str(raw.get("env_file"))

    ports, port_notes = _parse_ports(name, raw.get("ports"))
    unsupported.extend(port_notes)

    volumes, volume_notes = _parse_volumes(raw.get("volumes"), volume_names)
    unsupported.extend(volume_notes)

    runtime_user = _parse_user(raw.get("user"))

    health_check, health_notes = _parse_healthcheck(name, raw.get("healthcheck"))
    unsupported.extend(health_notes)

    depends_on, depends_notes = _parse_depends_on(name, raw.get("depends_on"))
    unsupported.extend(depends_notes)

    restart_policy = raw.get("restart")

    resources, deploy_notes = _parse_deploy(name, raw.get("deploy"))
    unsupported.extend(deploy_notes)

    labels = _parse_labels(raw.get("labels"))

    network_aliases, network_notes = _parse_networks(name, raw.get("networks"))
    unsupported.extend(network_notes)

    privileged = bool(raw.get("privileged", False))
    network_mode = raw.get("network_mode")

    unsupported.extend(
        f"services.{name}.{key}"
        for key in raw
        if key not in _KNOWN_SERVICE_FIELDS and not key.startswith("x-")
    )

    return ServiceDefinition(
        name=name,
        image=image,
        command=command,
        entrypoint=entrypoint,
        ports=ports,
        environment=environment,
        env_files=env_files,
        volumes=volumes,
        health_check=health_check,
        runtime_user=runtime_user,
        depends_on=depends_on,
        restart_policy=restart_policy,
        labels=labels,
        network_aliases=network_aliases,
        privileged=privileged,
        network_mode=network_mode,
        resources=resources,
        unsupported_fields=tuple(unsupported),
    )


def _parse_command_like(raw: Any) -> tuple[str, ...] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return tuple(shlex.split(raw))
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return None


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _parse_environment(raw: Any) -> tuple[EnvVar, ...]:
    if isinstance(raw, dict):
        return tuple(EnvVar(name=str(key), value=_stringify(value)) for key, value in raw.items())
    if isinstance(raw, list):
        result: list[EnvVar] = []
        for item in raw:
            text = str(item)
            if "=" in text:
                var_name, _, value = text.partition("=")
                result.append(EnvVar(name=var_name, value=value))
            else:
                result.append(EnvVar(name=text, value=None))
        return tuple(result)
    return ()


def _as_tuple_of_str(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return ()


def _split_port_host_ip(spec: str) -> tuple[str | None, str]:
    if spec.startswith("["):
        end = spec.find("]")
        if end == -1:
            return None, spec
        host_ip = spec[1:end]
        rest = spec[end + 1 :]
        if rest.startswith(":"):
            rest = rest[1:]
        return host_ip, rest

    parts = spec.split(":")
    if len(parts) == 3:
        return parts[0], f"{parts[1]}:{parts[2]}"
    return None, spec


def _parse_port_spec(index: int, spec: str) -> tuple[PortMapping | None, str | None]:
    protocol = Protocol.TCP
    body = spec
    if "/" in spec:
        body, _, proto_str = spec.rpartition("/")
        if proto_str.lower() == "udp":
            protocol = Protocol.UDP
        elif proto_str.lower() != "tcp":
            return None, f"ports[{index}]={spec!r} (unrecognized protocol)"

    host_ip, remainder = _split_port_host_ip(body)
    parts = remainder.split(":")

    if len(parts) == 1:
        host_port_str, container_port_str = None, parts[0]
    elif len(parts) == 2:
        host_port_str, container_port_str = parts
    else:
        return None, f"ports[{index}]={spec!r} (unrecognized syntax)"

    if _PORT_RANGE_PATTERN.match(container_port_str) or (
        host_port_str and _PORT_RANGE_PATTERN.match(host_port_str)
    ):
        return None, f"ports[{index}]={spec!r} (port ranges are not supported)"

    try:
        container_port = int(container_port_str)
        host_port = int(host_port_str) if host_port_str else None
    except ValueError:
        return None, f"ports[{index}]={spec!r} (unrecognized syntax)"

    note = None
    if host_ip and host_ip not in {"0.0.0.0", "::"}:
        note = f"ports[{index}].host_ip={host_ip}"

    return PortMapping(container_port=container_port, host_port=host_port, protocol=protocol), note


def _parse_long_port(index: int, entry: dict[Any, Any]) -> tuple[PortMapping | None, str | None]:
    target = entry.get("target")
    if target is None:
        return None, f"ports[{index}] (long syntax missing 'target')"

    published = entry.get("published")
    protocol = Protocol.UDP if str(entry.get("protocol", "tcp")).lower() == "udp" else Protocol.TCP

    published_str = str(published) if published is not None else None
    if published_str is not None and not published_str.isdigit():
        return None, f"ports[{index}].published={published_str!r} (port ranges are not supported)"

    mode = entry.get("mode")
    note = f"ports[{index}].mode={mode}" if mode and mode != "ingress" else None

    try:
        mapping = PortMapping(
            container_port=int(target),
            host_port=int(published_str) if published_str else None,
            protocol=protocol,
        )
    except (TypeError, ValueError):
        return None, f"ports[{index}] (unrecognized long syntax)"

    return mapping, note


def _parse_ports(service_name: str, raw: Any) -> tuple[tuple[PortMapping, ...], list[str]]:
    if raw is None:
        return (), []
    if not isinstance(raw, list):
        raise ParserError(f"service '{service_name}': 'ports' must be a list")

    mappings: list[PortMapping] = []
    unsupported: list[str] = []

    for index, entry in enumerate(raw):
        mapping: PortMapping | None
        note: str | None
        if isinstance(entry, dict):
            mapping, note = _parse_long_port(index, entry)
        elif isinstance(entry, str | int):
            mapping, note = _parse_port_spec(index, str(entry))
        else:
            mapping, note = None, f"ports[{index}] (unrecognized syntax)"

        if mapping is not None:
            mappings.append(mapping)
        if note:
            unsupported.append(note)

    return tuple(mappings), unsupported


def _looks_like_path(source: str) -> bool:
    return source.startswith(("/", "./", "../", "~"))


def _parse_short_volume(spec: str, volume_names: frozenset[str]) -> tuple[VolumeMount, str | None]:
    parts = spec.split(":")
    read_only = False
    if len(parts) > 1 and parts[-1] in {"ro", "rw"}:
        read_only = parts[-1] == "ro"
        parts = parts[:-1]

    if len(parts) == 1:
        return VolumeMount(
            source=None, target=parts[0], read_only=read_only, mount_type="volume"
        ), None

    source, target = parts[0], parts[1]
    is_named = not _looks_like_path(source)
    mount_type = "volume" if is_named else "bind"

    note = None
    if is_named and source not in volume_names:
        note = f"volumes references undeclared volume '{source}'"

    return (
        VolumeMount(
            source=source,
            target=target,
            read_only=read_only,
            mount_type=mount_type,
            is_named_volume=is_named,
        ),
        note,
    )


def _parse_long_volume(
    index: int, entry: dict[Any, Any], volume_names: frozenset[str]
) -> tuple[VolumeMount | None, str | None]:
    target = entry.get("target")
    if not target:
        return None, f"volumes[{index}] (long syntax missing 'target')"

    mount_type = entry.get("type", "volume")
    source = entry.get("source")
    read_only = bool(entry.get("read_only", False))

    if mount_type == "tmpfs":
        return VolumeMount(
            source=None, target=target, read_only=read_only, mount_type="tmpfs"
        ), None

    is_named = mount_type == "volume" and source is not None
    note = None
    if is_named and source not in volume_names:
        note = f"volumes[{index}] references undeclared volume '{source}'"

    return (
        VolumeMount(
            source=source,
            target=target,
            read_only=read_only,
            mount_type=mount_type,
            is_named_volume=is_named,
        ),
        note,
    )


def _parse_volumes(
    raw: Any, volume_names: frozenset[str]
) -> tuple[tuple[VolumeMount, ...], list[str]]:
    if raw is None:
        return (), []
    if not isinstance(raw, list):
        raise ParserError("'volumes' must be a list")

    mounts: list[VolumeMount] = []
    unsupported: list[str] = []

    for index, entry in enumerate(raw):
        mount: VolumeMount | None
        note: str | None
        if isinstance(entry, str):
            mount, note = _parse_short_volume(entry, volume_names)
        elif isinstance(entry, dict):
            mount, note = _parse_long_volume(index, entry, volume_names)
        else:
            mount, note = None, f"volumes[{index}] (unrecognized syntax)"

        if mount is not None:
            mounts.append(mount)
        if note:
            unsupported.append(note)

    return tuple(mounts), unsupported


def _parse_user(raw: Any) -> RuntimeUser | None:
    if raw is None:
        return None
    text = str(raw)
    uid_str, _, gid_str = text.partition(":")
    uid = int(uid_str) if uid_str.isdigit() else None
    gid = int(gid_str) if gid_str.isdigit() else None
    return RuntimeUser(uid=uid, gid=gid, raw=text)


def _parse_healthcheck(service_name: str, raw: Any) -> tuple[HealthCheck | None, list[str]]:
    if raw is None:
        return None, []
    if not isinstance(raw, dict):
        raise ParserError(f"service '{service_name}': 'healthcheck' must be a mapping")

    unsupported: list[str] = []
    test = raw.get("test")
    disabled = bool(raw.get("disable", False))

    test_value: tuple[str, ...] | str | None
    if isinstance(test, list):
        test_value = tuple(str(item) for item in test)
        if test_value == ("NONE",):
            disabled = True
    elif isinstance(test, str):
        test_value = test
    else:
        test_value = None

    def _duration(key: str) -> int | None:
        value = raw.get(key)
        if value is None:
            return None
        try:
            return parse_duration_to_seconds(str(value))
        except ValueError:
            unsupported.append(f"services.{service_name}.healthcheck.{key}={value!r}")
            return None

    healthcheck = HealthCheck(
        test=test_value,
        interval_seconds=_duration("interval"),
        timeout_seconds=_duration("timeout"),
        start_period_seconds=_duration("start_period"),
        retries=raw.get("retries"),
        disabled=disabled,
    )

    unsupported.extend(
        f"services.{service_name}.healthcheck.{key}"
        for key in raw
        if key not in _KNOWN_HEALTHCHECK_FIELDS
    )

    return healthcheck, unsupported


def _parse_depends_on(service_name: str, raw: Any) -> tuple[tuple[str, ...], list[str]]:
    if raw is None:
        return (), []
    if isinstance(raw, list):
        return tuple(str(item) for item in raw), []
    if isinstance(raw, dict):
        names: list[str] = []
        unsupported: list[str] = []
        for dep_name, dep_config in raw.items():
            names.append(str(dep_name))
            if isinstance(dep_config, dict):
                unsupported.extend(f"depends_on.{dep_name}.{key}" for key in dep_config)
        return tuple(names), unsupported
    raise ParserError(f"service '{service_name}': 'depends_on' must be a list or mapping")


def _parse_deploy(service_name: str, raw: Any) -> tuple[ResourceRequirements | None, list[str]]:
    if raw is None:
        return None, []
    if not isinstance(raw, dict):
        return None, [f"services.{service_name}.deploy"]

    unsupported: list[str] = [
        f"services.{service_name}.deploy.{key}" for key in raw if key != "resources"
    ]

    resources_raw = raw.get("resources")
    if not isinstance(resources_raw, dict):
        if resources_raw is not None:
            unsupported.append(f"services.{service_name}.deploy.resources")
        return None, unsupported

    reservations = resources_raw.get("reservations")
    limits = resources_raw.get("limits")
    reservations = reservations if isinstance(reservations, dict) else {}
    limits = limits if isinstance(limits, dict) else {}

    resources = ResourceRequirements(
        cpu_request=_stringify(reservations.get("cpus")),
        memory_request=_stringify(reservations.get("memory")),
        cpu_limit=_stringify(limits.get("cpus")),
        memory_limit=_stringify(limits.get("memory")),
    )

    unsupported.extend(
        f"services.{service_name}.deploy.resources.{key}"
        for key in resources_raw
        if key not in {"reservations", "limits"}
    )
    unsupported.extend(
        f"services.{service_name}.deploy.resources.reservations.{key}"
        for key in reservations
        if key not in {"cpus", "memory"}
    )
    unsupported.extend(
        f"services.{service_name}.deploy.resources.limits.{key}"
        for key in limits
        if key not in {"cpus", "memory"}
    )

    return resources, unsupported


def _parse_networks(service_name: str, raw: Any) -> tuple[tuple[str, ...], list[str]]:
    if raw is None or isinstance(raw, list):
        return (), []
    if not isinstance(raw, dict):
        raise ParserError(f"service '{service_name}': 'networks' must be a list or mapping")

    aliases: list[str] = []
    unsupported: list[str] = []
    for net_name, net_config in raw.items():
        if not isinstance(net_config, dict):
            continue
        net_aliases = net_config.get("aliases")
        if isinstance(net_aliases, list):
            aliases.extend(str(alias) for alias in net_aliases)
        unsupported.extend(
            f"services.{service_name}.networks.{net_name}.{key}"
            for key in net_config
            if key != "aliases"
        )

    return tuple(aliases), unsupported


def _parse_labels(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        return {str(key): str(value) for key, value in raw.items()}
    if isinstance(raw, list):
        labels: dict[str, str] = {}
        for item in raw:
            text = str(item)
            key, _, value = text.partition("=")
            labels[key] = value
        return labels
    return {}
