"""Flags environment variables that look like credentials.

No :class:`~gitops_scaffold.models.analysis.Finding` produced here ever
includes the actual variable value — only its name and a classification of
*how* the value was declared (literal / interpolated / empty / sourced from
the shell running Compose). See ``docs/compose-support.md`` for the four
value states this classification is based on.
"""

from __future__ import annotations

import re

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.config.settings import DEFAULT_SECRET_NAME_PATTERNS
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition

_INTERPOLATION_PATTERN = re.compile(r"^\$\{?[A-Za-z_][A-Za-z0-9_]*\}?$")


def looks_like_secret(name: str, patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS) -> bool:
    """Whether an environment variable name matches a configured secret pattern.

    Shared by this rule and :class:`~gitops_scaffold.reporting.report.Reporter`
    so both agree on what counts as secret-shaped.
    """
    upper_name = name.upper()
    return any(pattern.upper() in upper_name for pattern in patterns)


class SecretDetectionRule(DetectionRule):
    code = "secrets"

    def __init__(self, patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS) -> None:
        self._patterns = patterns

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        findings: list[Finding] = []

        for var in service.environment:
            if not looks_like_secret(var.name, self._patterns):
                continue

            field_path = f"environment.{var.name}"
            if var.value is None:
                findings.append(
                    Finding(
                        code="secret-shell-passthrough",
                        message=(
                            f"Service '{service.name}' declares '{var.name}' with no value "
                            "in this file — it will be sourced from the environment running "
                            "Compose."
                        ),
                        severity=Severity.INFO,
                        service_name=service.name,
                        field_path=field_path,
                        remediation=(
                            "Ensure this is supplied via a secret manager wherever "
                            "Compose is actually run."
                        ),
                    )
                )
            elif var.value == "":
                findings.append(
                    Finding(
                        code="secret-empty",
                        message=f"Service '{service.name}' declares '{var.name}' as an empty placeholder.",
                        severity=Severity.WARNING,
                        service_name=service.name,
                        field_path=field_path,
                        remediation="Populate this value via a secret manager before deploying.",
                    )
                )
            elif _INTERPOLATION_PATTERN.match(var.value):
                findings.append(
                    Finding(
                        code="secret-interpolated",
                        message=(
                            f"Service '{service.name}' sources '{var.name}' from variable "
                            "interpolation, not a literal value."
                        ),
                        severity=Severity.INFO,
                        service_name=service.name,
                        field_path=field_path,
                        remediation=(
                            "Good practice — ensure the real value is injected via a secret "
                            "manager, not committed to source control."
                        ),
                    )
                )
            else:
                findings.append(
                    Finding(
                        code="secret-literal-value",
                        message=(
                            f"Service '{service.name}' declares '{var.name}' with a literal "
                            "value committed to the compose file. Never commit secret values "
                            "to source control."
                        ),
                        severity=Severity.CRITICAL,
                        service_name=service.name,
                        field_path=field_path,
                        remediation=(
                            "Remove the literal value and supply it via a secret manager "
                            "(never a plaintext Kubernetes Secret either)."
                        ),
                    )
                )

        if service.env_files:
            findings.append(
                Finding(
                    code="secret-env-file-reference",
                    message=(
                        f"Service '{service.name}' references env_file(s) "
                        f"{', '.join(service.env_files)} — contents are not inspected."
                    ),
                    severity=Severity.INFO,
                    service_name=service.name,
                    field_path="env_file",
                    remediation="Review the referenced file(s) yourself for secrets before deploying.",
                )
            )

        return tuple(findings)
