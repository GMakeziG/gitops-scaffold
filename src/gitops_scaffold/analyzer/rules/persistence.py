"""Flags services needing persistent storage that Compose can't size for us.

Bind mounts and tmpfs are out of scope here — see ``analyzer/rules/volumes.py``,
which owns those. This rule only covers named-volume mounts.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class PersistenceDetectionRule(DetectionRule):
    code = "persistence"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []
        for index, volume in enumerate(service.volumes):
            is_named = volume.mount_type == "volume" and volume.source is not None
            if is_named and not volume.read_only:
                findings.append(
                    Finding(
                        code="persistence-storage-size-unknown",
                        message=(
                            f"Service '{service.name}' needs persistent storage for "
                            f"'{volume.target}' — Compose doesn't declare a size, so a "
                            "generated PVC will need review."
                        ),
                        severity=Severity.WARNING,
                        service_name=service.name,
                        field_path=f"volumes[{index}]",
                        remediation="Set an explicit storage size when generating the PVC.",
                    )
                )
        return tuple(findings)
