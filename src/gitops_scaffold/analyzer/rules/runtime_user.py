"""Flags the runtime user a service's container runs as."""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


class RuntimeUserDetectionRule(DetectionRule):
    code = "runtime-user"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        user = service.runtime_user

        if user is None:
            return (
                Finding(
                    code="runtime-user-unspecified",
                    message=(
                        f"Service '{service.name}' declares no user — it will run as the "
                        "image's default user (often root)."
                    ),
                    severity=Severity.WARNING,
                    service_name=service.name,
                    field_path="user",
                    remediation="Set an explicit non-root user.",
                ),
            )

        if user.uid == 0:
            return (
                Finding(
                    code="runtime-user-root",
                    message=f"Service '{service.name}' explicitly runs as UID 0 (root).",
                    severity=Severity.CRITICAL,
                    service_name=service.name,
                    field_path="user",
                    remediation="Run as a non-root user.",
                ),
            )

        if user.uid is None:
            return (
                Finding(
                    code="runtime-user-unresolved",
                    message=(
                        f"Service '{service.name}' declares user '{user.raw}' by name — "
                        "numeric UID/GID could not be resolved without inspecting the image."
                    ),
                    severity=Severity.WARNING,
                    service_name=service.name,
                    field_path="user",
                    remediation=(
                        "Use a numeric UID (and GID) so Kubernetes securityContext can be "
                        "set precisely."
                    ),
                ),
            )

        gid_suffix = f":{user.gid}" if user.gid is not None else ""
        return (
            Finding(
                code="runtime-user-detected",
                message=f"Service '{service.name}' runs as UID {user.uid}{gid_suffix}.",
                severity=Severity.INFO,
                service_name=service.name,
                field_path="user",
            ),
        )
