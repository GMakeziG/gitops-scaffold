"""Shared, deterministic volume-to-PVC planning.

This is where the deliberate v0.2→v0.3 behavior change lives: v0.2's
``VolumeDetectionRule`` treats every bind mount as warning-only, no PVC. v0.3
converts bind mounts representing real application data into PVC scaffolding
too (marked ``REVIEW REQUIRED`` — the data currently lives on the host and
needs migration), while host-system paths, known single-file mounts, tmpfs,
and ambiguous file-looking mounts are excluded. See ``docs/generation.md``
for the full rationale and permanent limitations (there is no way to inspect
the real host filesystem to know for certain whether a bind mount target is
a file or a directory).

A Compose *named* volume is identified by its ``source`` string and can be
mounted by more than one service (e.g. an app and a backup sidecar sharing
one volume) — those get exactly one shared PVC, not one per service that
mounts it, which is why this module plans across the whole
``ApplicationDefinition`` rather than one service at a time.
"""

from __future__ import annotations

from dataclasses import dataclass

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition, VolumeMount
from gitops_scaffold.models.generation import GenerationNote, GenerationNoteCategory
from gitops_scaffold.utils.naming import k8s_resource_name

_HOST_SYSTEM_PATH_PREFIXES = (
    "/proc",
    "/sys",
    "/dev",
    "/var/run/docker.sock",
    "/run/docker.sock",
)
_SINGLE_FILE_MOUNT_TARGETS = frozenset(
    {"/etc/localtime", "/etc/timezone", "/etc/hosts", "/etc/resolv.conf"}
)


@dataclass(frozen=True)
class PlannedPVC:
    """One PersistentVolumeClaim to render, plus its provenance for documentation."""

    name: str
    target: str
    source_description: str
    read_only: bool
    shared: bool
    service_names: tuple[str, ...]


@dataclass(frozen=True)
class PlannedMount:
    """One volumeMount entry a Deployment container should render."""

    pvc_name: str
    target: str
    read_only: bool


@dataclass(frozen=True)
class VolumePlan:
    #: PVCs shared by more than one service, or simply app-scoped by
    #: identity (a named volume) rather than service-scoped — rendered at
    #: the output root regardless of layout mode.
    shared_pvcs: tuple[PlannedPVC, ...]
    #: PVCs scoped to one service (bind-mount- or anonymous-volume-derived).
    service_pvcs: dict[str, tuple[PlannedPVC, ...]]
    #: Every volumeMount a service's Deployment container should render —
    #: only ever references a PVC that was actually planned (excluded
    #: mounts get no volumeMount at all, nothing to mount).
    service_mounts: dict[str, tuple[PlannedMount, ...]]
    notes: tuple[GenerationNote, ...]


def _is_host_system_path(volume: VolumeMount) -> bool:
    if volume.target in _SINGLE_FILE_MOUNT_TARGETS:
        return True
    candidates = [volume.target, *([volume.source] if volume.source else [])]
    return any(
        candidate.startswith(prefix)
        for candidate in candidates
        for prefix in _HOST_SYSTEM_PATH_PREFIXES
    )


def _looks_like_ambiguous_file_mount(volume: VolumeMount) -> bool:
    if volume.target in _SINGLE_FILE_MOUNT_TARGETS:
        return False  # already excluded outright above; don't double-report
    last_segment = volume.target.rsplit("/", 1)[-1]
    return volume.read_only and "." in last_segment


def plan_volumes(app: ApplicationDefinition, settings: ScaffoldSettings) -> VolumePlan:
    notes: list[GenerationNote] = []
    shared_sources: dict[str, list[tuple[ServiceDefinition, VolumeMount]]] = {}
    service_pvcs: dict[str, list[PlannedPVC]] = {service.name: [] for service in app.services}
    service_mounts: dict[str, list[PlannedMount]] = {service.name: [] for service in app.services}

    for service in app.services:
        for volume in service.volumes:
            is_named = volume.mount_type == "volume" and volume.source is not None
            is_anonymous = volume.mount_type == "volume" and volume.source is None
            is_bind = volume.mount_type == "bind"
            is_tmpfs = volume.mount_type == "tmpfs"

            if is_tmpfs:
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.SKIPPED,
                        message=(
                            f"tmpfs mount at '{volume.target}' is ephemeral by definition — "
                            "no PVC generated."
                        ),
                        service_name=service.name,
                    )
                )
                continue

            if is_named:
                assert volume.source is not None
                shared_sources.setdefault(volume.source, []).append((service, volume))
                continue

            if is_bind:
                if _is_host_system_path(volume):
                    notes.append(
                        GenerationNote(
                            category=GenerationNoteCategory.SKIPPED,
                            message=(
                                f"Bind mount '{volume.source}' -> '{volume.target}' looks like "
                                "a host-system path — not converted to a PVC."
                            ),
                            service_name=service.name,
                        )
                    )
                    continue
                if _looks_like_ambiguous_file_mount(volume):
                    notes.append(
                        GenerationNote(
                            category=GenerationNoteCategory.SKIPPED,
                            message=(
                                f"Bind mount '{volume.source}' -> '{volume.target}' looks like "
                                "a single config file, not a data directory — not converted to "
                                "a PVC. A ConfigMap or Secret volume may fit better; this can't "
                                "be determined without inspecting the host filesystem."
                            ),
                            service_name=service.name,
                            requires_review=True,
                        )
                    )
                    continue

                pvc_name = k8s_resource_name(service.name, volume.target)
                service_pvcs[service.name].append(
                    PlannedPVC(
                        name=pvc_name,
                        target=volume.target,
                        source_description=f"bind mount {volume.source}",
                        read_only=volume.read_only,
                        shared=False,
                        service_names=(service.name,),
                    )
                )
                service_mounts[service.name].append(
                    PlannedMount(
                        pvc_name=pvc_name, target=volume.target, read_only=volume.read_only
                    )
                )
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Bind mount '{volume.source}' -> '{volume.target}' converted to PVC "
                            f"scaffolding '{pvc_name}' — the data currently lives on the host and "
                            "must be migrated into the PVC."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )
                continue

            if is_anonymous:
                pvc_name = k8s_resource_name(service.name, volume.target)
                service_pvcs[service.name].append(
                    PlannedPVC(
                        name=pvc_name,
                        target=volume.target,
                        source_description="anonymous volume",
                        read_only=volume.read_only,
                        shared=False,
                        service_names=(service.name,),
                    )
                )
                service_mounts[service.name].append(
                    PlannedMount(
                        pvc_name=pvc_name, target=volume.target, read_only=volume.read_only
                    )
                )
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Anonymous volume at '{volume.target}' converted to PVC scaffolding "
                            f"'{pvc_name}' — confirm persistence was actually intended here."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )

    # A named volume used by exactly one service belongs in *that service's*
    # own PVC bucket, not the root -- "shared" (and root-level) only applies
    # when 2+ services actually mount the same Compose volume.
    shared_pvcs: list[PlannedPVC] = []
    for source, entries in shared_sources.items():
        name = k8s_resource_name(source)
        service_names = tuple(service.name for service, _ in entries)
        is_shared = len(service_names) > 1
        description = f"named volume '{source}'"
        if is_shared:
            description += f" (shared by: {', '.join(service_names)})"
        pvc = PlannedPVC(
            name=name,
            target=entries[0][1].target,
            source_description=description,
            read_only=all(volume.read_only for _, volume in entries),
            shared=is_shared,
            service_names=service_names,
        )
        if is_shared:
            shared_pvcs.append(pvc)
        else:
            service_pvcs[service_names[0]].append(pvc)
        for service, volume in entries:
            service_mounts[service.name].append(
                PlannedMount(pvc_name=name, target=volume.target, read_only=volume.read_only)
            )
        if is_shared:
            notes.append(
                GenerationNote(
                    category=GenerationNoteCategory.ASSUMPTION,
                    message=(
                        f"Named volume '{source}' is mounted by multiple services "
                        f"({', '.join(service_names)}) — generated as a single shared PVC "
                        f"'{name}' rather than one per service."
                    ),
                )
            )

    return VolumePlan(
        shared_pvcs=tuple(shared_pvcs),
        service_pvcs={name: tuple(pvcs) for name, pvcs in service_pvcs.items()},
        service_mounts={name: tuple(mounts) for name, mounts in service_mounts.items()},
        notes=tuple(notes),
    )
