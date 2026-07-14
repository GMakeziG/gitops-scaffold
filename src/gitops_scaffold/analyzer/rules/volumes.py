"""Flags volume mounts by kind: bind mount, named volume, anonymous volume, tmpfs."""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class VolumeDetectionRule(DetectionRule):
    code = "volumes"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for index, volume in enumerate(service.volumes):
            field_path = f"volumes[{index}]"

            if volume.mount_type == "bind":
                findings.append(
                    Finding(
                        code="volume-bind-mount",
                        message=(
                            f"Service '{service.name}' bind-mounts host path "
                            f"'{volume.source}' to '{volume.target}' — host paths don't "
                            "translate to Kubernetes."
                        ),
                        severity=Severity.WARNING,
                        service_name=service.name,
                        field_path=field_path,
                        remediation=(
                            "Replace with a named volume/PVC, or an init step that "
                            "populates the data in-cluster."
                        ),
                    )
                )
            elif volume.mount_type == "volume" and volume.source is None:
                findings.append(
                    Finding(
                        code="volume-anonymous",
                        message=(
                            f"Service '{service.name}' mounts an anonymous volume at "
                            f"'{volume.target}' — less durable than a named volume."
                        ),
                        severity=Severity.WARNING,
                        service_name=service.name,
                        field_path=field_path,
                        remediation="Give the volume a name so it can be reliably provisioned as a PVC.",
                    )
                )
            elif volume.mount_type == "volume":
                findings.append(
                    Finding(
                        code="volume-named",
                        message=(
                            f"Service '{service.name}' mounts named volume '{volume.source}' "
                            f"at '{volume.target}' — will require a PersistentVolumeClaim."
                        ),
                        severity=Severity.INFO,
                        service_name=service.name,
                        field_path=field_path,
                    )
                )
            elif volume.mount_type == "tmpfs":
                findings.append(
                    Finding(
                        code="volume-tmpfs",
                        message=(
                            f"Service '{service.name}' mounts a tmpfs (ephemeral, in-memory) "
                            f"volume at '{volume.target}' — no persistence needed."
                        ),
                        severity=Severity.INFO,
                        service_name=service.name,
                        field_path=field_path,
                    )
                )
        return tuple(findings)
