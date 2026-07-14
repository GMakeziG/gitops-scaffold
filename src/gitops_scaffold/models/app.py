"""The application intermediate representation (IR).

This is the normalized model that every parser must produce and every
analyzer, generator, and validator consumes. Keeping this model free of any
Docker-Compose-specific (or Helm-specific, etc.) concepts is what lets new
input formats be added later without touching analyzers or generators.

Fields here only ever hold what a parser could directly observe. Value
judgments ("this is a security risk", "this tag is bad practice") never live
here — they belong to ``analyzer/rules/*.py``, which turns observations into
:class:`~gitops_scaffold.models.analysis.Finding`\\ s. ``unsupported_fields``
on :class:`ServiceDefinition` and :class:`ApplicationDefinition` records
dotted paths (e.g. ``"services.web.cap_add"``) for anything a parser saw but
doesn't model, so nothing is silently dropped — see ``docs/compose-support.md``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Protocol(StrEnum):
    """Transport protocol for an exposed port."""

    TCP = "TCP"
    UDP = "UDP"


class PortMapping(BaseModel):
    """A single port exposed by a service."""

    model_config = ConfigDict(frozen=True)

    container_port: int
    host_port: int | None = None
    protocol: Protocol = Protocol.TCP
    name: str | None = None


class EnvVar(BaseModel):
    """A single environment variable declared on a service.

    ``value`` preserves exactly what was written (or ``None`` if the
    variable was declared with no value at all — see
    ``docs/compose-support.md`` for the four value states Compose allows).
    Classifying a variable as secret-like is an analysis concern, not a
    parsing one — see ``analyzer/rules/secrets.py``.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: str | None = None


class VolumeMount(BaseModel):
    """A filesystem mount attached to a service.

    ``mount_type`` is one of ``"bind"``, ``"volume"``, or ``"tmpfs"``.
    An anonymous volume (``volumes: ["/data"]``, no name) is
    ``mount_type == "volume"`` with ``source is None``; a named volume has
    both set. ``is_named_volume`` is kept for convenience, derived as
    ``mount_type == "volume" and source is not None``.
    """

    model_config = ConfigDict(frozen=True)

    source: str | None
    target: str
    read_only: bool = False
    is_named_volume: bool = False
    mount_type: str | None = None


class HealthCheck(BaseModel):
    """A health check declared on a service, if any.

    ``disabled`` is set when Compose's ``test: ["NONE"]`` or
    ``disable: true`` is used — a deliberate opt-out, distinct from a
    service that simply declares no health check at all.
    """

    model_config = ConfigDict(frozen=True)

    test: tuple[str, ...] | str | None = None
    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    start_period_seconds: int | None = None
    retries: int | None = None
    disabled: bool = False


class RuntimeUser(BaseModel):
    """The user/group a service's container runs as, if it can be determined.

    ``uid``/``gid`` resolve independently: ``user: "1000:appgroup"`` yields
    ``uid=1000, gid=None`` (the group name can't be resolved to a numeric
    ID without inspecting the image). ``raw`` always preserves the original
    declared string so nothing observed is silently dropped, even when
    neither side resolves to a number (``user: appuser``).
    """

    model_config = ConfigDict(frozen=True)

    uid: int | None = None
    gid: int | None = None
    raw: str | None = None


class ResourceRequirements(BaseModel):
    """Compute resource requests/limits declared under ``deploy.resources``.

    Stored as the raw strings Compose uses (e.g. ``"0.50"``, ``"512M"``) —
    converting to Kubernetes resource units is a generator (v0.3) concern,
    not a parsing one.
    """

    model_config = ConfigDict(frozen=True)

    cpu_request: str | None = None
    cpu_limit: str | None = None
    memory_request: str | None = None
    memory_limit: str | None = None


class ServiceDefinition(BaseModel):
    """A single deployable unit within an application (one container image)."""

    model_config = ConfigDict(frozen=True)

    name: str
    image: str | None = None
    command: tuple[str, ...] | None = None
    entrypoint: tuple[str, ...] | None = None
    ports: tuple[PortMapping, ...] = Field(default_factory=tuple)
    environment: tuple[EnvVar, ...] = Field(default_factory=tuple)
    env_files: tuple[str, ...] = Field(default_factory=tuple)
    volumes: tuple[VolumeMount, ...] = Field(default_factory=tuple)
    health_check: HealthCheck | None = None
    runtime_user: RuntimeUser | None = None
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    restart_policy: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    network_aliases: tuple[str, ...] = Field(default_factory=tuple)
    privileged: bool = False
    network_mode: str | None = None
    resources: ResourceRequirements | None = None
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)


class ApplicationDefinition(BaseModel):
    """The full, normalized application: one or more services plus provenance."""

    model_config = ConfigDict(frozen=True)

    name: str
    services: tuple[ServiceDefinition, ...]
    source_format: str
    source_path: str | None = None
    unsupported_fields: tuple[str, ...] = Field(default_factory=tuple)
