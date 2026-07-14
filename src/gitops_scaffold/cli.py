"""Command-line interface for gitops-scaffold.

Three top-level commands, matching the three stages of the pipeline
described in ``docs/architecture.md``:

- ``analyze``:  parse + analyze, print a confidence report. No files written
  unless ``--output`` is given, in which case the full analysis is also
  saved as JSON — the same schema ``generate`` is expected to accept as
  cached input in v0.3 (see ``docs/roadmap.md``).
- ``generate``: parse + analyze + generate manifests to an output directory.
  Still stubbed — v0.3.
- ``validate``: check a previously generated output directory for structural
  issues (missing files, unresolved review markers).

Exit codes for ``analyze``: **1** means the input couldn't be parsed at all
(bad path, unrecognized format, malformed Compose); **2** means analysis
completed but found at least one CRITICAL finding; **0** means analysis
completed with only INFO/WARNING findings (or none).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console

from gitops_scaffold import __version__
from gitops_scaffold.analyzer.default import DefaultAnalyzer
from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.report import AnalysisReport
from gitops_scaffold.parsers.base import ParserError
from gitops_scaffold.parsers.registry import detect_parser
from gitops_scaffold.reporting.report import Reporter, redact_application
from gitops_scaffold.utils.fs import write_file
from gitops_scaffold.utils.logging import configure_logging
from gitops_scaffold.validators.structure import StructureValidator

app = typer.Typer(
    name="gitops-scaffold",
    help="Analyze application definitions and generate opinionated, production-ready GitOps manifests.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"gitops-scaffold [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """gitops-scaffold: an extensible GitOps scaffolding platform."""
    configure_logging(verbose=verbose)


@app.command()
def analyze(
    source: Path = typer.Argument(
        ...,
        help="Path to an application definition, e.g. docker-compose.yml",
    ),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TABLE,
        "--format",
        "-f",
        help="How to render the report to the console.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write the full analysis as JSON to this path (in addition to the console report).",
    ),
) -> None:
    """Analyze an application definition and print a confidence report."""
    if not source.exists():
        console.print(f"[red]Error:[/red] {source} does not exist.")
        raise typer.Exit(code=1)

    try:
        parser = detect_parser(source)
        application = parser.parse(source)
    except ParserError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    settings = ScaffoldSettings.load(source.parent / ".gitops-scaffold.yaml")
    result = DefaultAnalyzer(settings).analyze(application)

    # Analysis itself runs against the real values (it has to, to classify
    # them) -- only what gets printed or written is redacted.
    redacted_application = redact_application(application, settings.secret_name_patterns)

    if output_format is OutputFormat.JSON:
        report = AnalysisReport(application=redacted_application, analysis=result)
        console.print_json(data=report.model_dump(mode="json"), sort_keys=False)
    else:
        Reporter(console=console, secret_patterns=settings.secret_name_patterns).render(
            application, result
        )

    if output is not None:
        report = AnalysisReport(application=redacted_application, analysis=result)
        write_file(output, report.model_dump_json(indent=2) + "\n", overwrite=True)
        console.print(f"[green]Analysis written to {output}[/green]")

    if result.criticals:
        raise typer.Exit(code=2)
    raise typer.Exit(code=0)


@app.command()
def generate(
    source: Path = typer.Argument(
        ...,
        exists=True,
        help=(
            "Path to an application definition (e.g. docker-compose.yml) or, in a future "
            "release, a saved analysis report produced by 'analyze --output'."
        ),
    ),
    output: Path = typer.Option(
        Path("./gitops"),
        "--output",
        "-o",
        help="Directory to write generated manifests to.",
    ),
) -> None:
    """Generate GitOps manifests from an application definition."""
    console.print(
        "[yellow]Manifest generation is not yet implemented.[/yellow] "
        "See docs/roadmap.md for the v0.3 milestone."
    )
    console.print(f"Source provided: [bold]{source}[/bold], output: [bold]{output}[/bold]")
    raise typer.Exit(code=1)


@app.command()
def validate(
    output_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Directory containing previously generated GitOps manifests.",
    ),
) -> None:
    """Validate a generated GitOps output directory's structure."""
    validator = StructureValidator()
    findings = validator.validate(output_dir)

    if not findings:
        console.print(f"[green]No structural issues found in {output_dir}[/green]")
        return

    for finding in findings:
        color = "red" if finding.severity.value == "critical" else "yellow"
        console.print(f"[{color}]{finding.severity.value.upper()}[/{color}] {finding.message}")

    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
