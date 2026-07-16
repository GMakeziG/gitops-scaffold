"""Shared, deterministic container-port planning.

Used by both ``DeploymentGenerator`` and ``ServiceGenerator`` so a
container's named ports and a Service's ``targetPort`` references are
derived from the exact same computation and can never drift apart. Only
ever operates on ``PortMapping.container_port`` — Compose's ``host_port``
never enters this module at all, since it has no Kubernetes equivalent.
"""

from __future__ import annotations

from dataclasses import dataclass

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.app import ServiceDefinition
from gitops_scaffold.models.generation import GenerationNote, GenerationNoteCategory
from gitops_scaffold.utils.naming import MAX_PORT_NAME_LENGTH, kebab_case


@dataclass(frozen=True)
class PlannedPort:
    """One container port, ready to render into both a Deployment and a Service."""

    name: str
    container_port: int
    protocol: str  # "TCP" | "UDP"


@dataclass(frozen=True)
class PortPlan:
    ports: tuple[PlannedPort, ...]
    notes: tuple[GenerationNote, ...]


def _base_name(protocol: str, container_port: int) -> str:
    return kebab_case(f"{protocol.lower()}-{container_port}")


def _unique_name(base_name: str, taken: set[str]) -> str:
    name = base_name[:MAX_PORT_NAME_LENGTH]
    if name not in taken:
        return name
    for suffix in range(2, 100):
        candidate = f"{suffix}"
        truncated = f"{base_name[: MAX_PORT_NAME_LENGTH - len(candidate) - 1]}-{candidate}"
        if truncated not in taken:
            return truncated
    raise ValueError(f"could not derive a unique port name from {base_name!r}")


def plan_ports(service: ServiceDefinition, settings: ScaffoldSettings) -> PortPlan:
    """Builds the deterministic, named port list for ``service``.

    Applies ``settings.port_overrides`` only when the service has exactly
    one parsed port — with zero or multiple ports, an override is ambiguous
    (which port would it replace?) and is ignored, with a note, rather than
    guessed.
    """
    notes: list[GenerationNote] = []
    ports = list(service.ports)

    override = settings.port_overrides.get(service.name)
    if override is not None:
        if len(ports) == 1:
            original = ports[0]
            ports = [original.model_copy(update={"container_port": override})]
            notes.append(
                GenerationNote(
                    category=GenerationNoteCategory.ASSUMPTION,
                    message=(
                        f"Container port overridden to {override} via configured "
                        f"port_overrides (was {original.container_port})."
                    ),
                    service_name=service.name,
                )
            )
        else:
            notes.append(
                GenerationNote(
                    category=GenerationNoteCategory.SKIPPED,
                    message=(
                        f"port_overrides entry for '{service.name}' ignored: applies only "
                        f"when a service has exactly one port (found {len(ports)})."
                    ),
                    service_name=service.name,
                    requires_review=True,
                )
            )

    planned: list[PlannedPort] = []
    taken: set[str] = set()
    for port in ports:
        base = (
            kebab_case(port.name)
            if port.name
            else _base_name(port.protocol.value, port.container_port)
        )
        name = _unique_name(base, taken)
        taken.add(name)
        planned.append(
            PlannedPort(name=name, container_port=port.container_port, protocol=port.protocol.value)
        )

    return PortPlan(ports=tuple(planned), notes=tuple(notes))
