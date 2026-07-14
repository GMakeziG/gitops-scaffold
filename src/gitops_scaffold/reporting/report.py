"""Renders an :class:`AnalysisResult` as a human-readable Rich report.

This is deliberately generic over whatever findings an analyzer produces —
it has no knowledge of Docker Compose or any other input format, so it works
unchanged once real analyzers land in v0.2.
"""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from gitops_scaffold.models.analysis import AnalysisResult, Severity

_SEVERITY_STYLE: dict[Severity, tuple[str, str]] = {
    Severity.INFO: ("green", "✔"),  # ✔
    Severity.WARNING: ("yellow", "⚠"),  # ⚠
    Severity.CRITICAL: ("red", "✖"),  # ✖
}


class Reporter:
    """Renders analysis results to a Rich :class:`~rich.console.Console`."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render(self, result: AnalysisResult) -> None:
        """Print a checklist-style report followed by a confidence score."""
        lines: list[Text] = []
        for finding in result.findings:
            color, glyph = _SEVERITY_STYLE[finding.severity]
            line = Text(f"{glyph} ", style=color)
            line.append(finding.message)
            if finding.remediation:
                line.append(f"  ({finding.remediation})", style="dim")
            lines.append(line)

        if not lines:
            lines.append(Text("No findings.", style="dim"))

        confidence_color = self._confidence_color(result.confidence)
        footer = Text(
            f"\nConfidence: {result.confidence_percent}%", style=f"bold {confidence_color}"
        )

        self.console.print(
            Panel(
                Group(*lines, footer),
                title=f"gitops-scaffold report: {result.application_name}",
                border_style="blue",
            )
        )

    @staticmethod
    def _confidence_color(confidence: float) -> str:
        if confidence >= 0.85:
            return "green"
        if confidence >= 0.6:
            return "yellow"
        return "red"
