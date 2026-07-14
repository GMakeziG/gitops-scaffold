"""Renders an :class:`ApplicationDefinition` + :class:`AnalysisResult` as a
human-readable Rich report.

The "detected: services/images/ports/..." inventory is read directly from
the IR (``ApplicationDefinition`` never changes shape based on which
analyzer ran); findings/confidence come from ``AnalysisResult``. Env var
values are redacted here using the same
:func:`~gitops_scaffold.analyzer.rules.secrets.looks_like_secret` predicate
the secret-detection rule itself uses — single source of truth for what
counts as secret-shaped, so the report can never accidentally print a value
the analyzer considers a secret.
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from gitops_scaffold.analyzer.rules.secrets import looks_like_secret
from gitops_scaffold.config.settings import DEFAULT_SECRET_NAME_PATTERNS
from gitops_scaffold.models.analysis import AnalysisResult, Severity
from gitops_scaffold.models.app import ApplicationDefinition

_SEVERITY_STYLE: dict[Severity, tuple[str, str]] = {
    Severity.INFO: ("green", "✔"),
    Severity.WARNING: ("yellow", "⚠"),
    Severity.CRITICAL: ("red", "✖"),
}

_REDACTED = "***REDACTED***"


def redact_application(
    app: ApplicationDefinition, secret_patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS
) -> ApplicationDefinition:
    """Returns a copy of ``app`` with secret-shaped environment variable values redacted.

    Use this at any output boundary (``--format json``, ``--output``) — never
    for the copy of the IR the analyzer itself runs against, which needs the
    real values to classify them in the first place.
    """
    redacted_services = tuple(
        service.model_copy(
            update={
                "environment": tuple(
                    var.model_copy(update={"value": _REDACTED})
                    if var.value and looks_like_secret(var.name, secret_patterns)
                    else var
                    for var in service.environment
                )
            }
        )
        for service in app.services
    )
    return app.model_copy(update={"services": redacted_services})


class Reporter:
    """Renders an application + its analysis to a Rich :class:`~rich.console.Console`."""

    def __init__(
        self,
        console: Console | None = None,
        secret_patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS,
    ) -> None:
        self.console = console or Console()
        self._secret_patterns = secret_patterns

    def render(self, app: ApplicationDefinition, result: AnalysisResult) -> None:
        """Print the inventory detected in ``app`` plus ``result``'s findings/confidence."""
        confidence_color = self._confidence_color(result.confidence)
        footer = Text(
            f"\nConfidence: {result.confidence_percent}%", style=f"bold {confidence_color}"
        )

        self.console.print(
            Panel(
                Group(self._render_inventory(app), *self._render_findings(result), footer),
                title=f"gitops-scaffold report: {result.application_name}",
                border_style="blue",
            )
        )

    def _render_inventory(self, app: ApplicationDefinition) -> Group:
        lines: list[Text] = []

        if not app.services:
            return Group(Text("No services detected.", style="dim"))

        for service in app.services:
            lines.append(Text(f"Service: {service.name}", style="bold"))
            lines.append(Text(f"  Image: {service.image or '(none)'}"))

            if service.ports:
                ports = ", ".join(
                    f"{port.host_port or '?'}->{port.container_port}/{port.protocol.value}"
                    for port in service.ports
                )
                lines.append(Text(f"  Ports: {ports}"))

            if service.environment:
                rendered_vars = [
                    f"{var.name}={_REDACTED}"
                    if looks_like_secret(var.name, self._secret_patterns)
                    else f"{var.name}={var.value}"
                    for var in service.environment
                ]
                lines.append(Text(f"  Environment: {', '.join(rendered_vars)}"))

            if service.volumes:
                volumes = ", ".join(
                    f"{volume.source or '(anonymous)'}->{volume.target}"
                    for volume in service.volumes
                )
                lines.append(Text(f"  Volumes: {volumes}"))

            health_summary = "configured" if service.health_check is not None else "none"
            lines.append(Text(f"  Health check: {health_summary}"))

            user_summary = service.runtime_user.raw if service.runtime_user else "unspecified"
            lines.append(Text(f"  Runtime user: {user_summary}"))

            if service.depends_on:
                lines.append(Text(f"  Depends on: {', '.join(service.depends_on)}"))

        return Group(*lines)

    def _render_findings(self, result: AnalysisResult) -> list[Text]:
        lines: list[Text] = [Text("")]

        if not result.findings:
            lines.append(Text("No findings.", style="dim"))
            return lines

        for finding in result.findings:
            color, glyph = _SEVERITY_STYLE[finding.severity]
            line = Text(f"{glyph} ", style=color)
            line.append(finding.message)
            if finding.remediation:
                line.append(f"  ({finding.remediation})", style="dim")
            lines.append(line)

        return lines

    @staticmethod
    def _confidence_color(confidence: float) -> str:
        if confidence >= 0.85:
            return "green"
        if confidence >= 0.6:
            return "yellow"
        return "red"
