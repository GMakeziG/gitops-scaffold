"""The application intermediate representation (IR).

This is the normalized model that every parser must produce and every
analyzer, generator, and validator consumes. Keeping this model free of any
Docker-Compose-specific (or Helm-specific, etc.) concepts is what lets new
input formats be added later without touching analyzers or generators.
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

    ``is_secret`` is a hint set by the analyzer's secret-detection rules
    (see ``analyzer/rules/secrets.py``), not by the parser. Parsers should
    always leave it at the default and let the analyzer decide.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    value: str | None = None
    is_secret: bool = False


class VolumeMount(BaseModel):
    """A filesystem mount attached to a service."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    read_only: bool = False
    is_named_volume: bool = False


class HealthCheck(BaseModel):
    """A health check declared on a service, if any."""

    model_config = ConfigDict(frozen=True)

    test: tuple[str, ...] | str | None = None
    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    retries: int | None = None


class RuntimeUser(BaseModel):
    """The user/group a service's container runs as, if it can be determined."""

    model_config = ConfigDict(frozen=True)

    uid: int | None = None
    gid: int | None = None


class ServiceDefinition(BaseModel):
    """A single deployable unit within an application (one container image)."""

    model_config = ConfigDict(frozen=True)

    name: str
    image: str
    command: tuple[str, ...] | None = None
    ports: tuple[PortMapping, ...] = Field(default_factory=tuple)
    environment: tuple[EnvVar, ...] = Field(default_factory=tuple)
    volumes: tuple[VolumeMount, ...] = Field(default_factory=tuple)
    health_check: HealthCheck | None = None
    runtime_user: RuntimeUser | None = None
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    restart_policy: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ApplicationDefinition(BaseModel):
    """The full, normalized application: one or more services plus provenance."""

    model_config = ConfigDict(frozen=True)

    name: str
    services: tuple[ServiceDefinition, ...]
    source_format: str
    source_path: str | None = None
