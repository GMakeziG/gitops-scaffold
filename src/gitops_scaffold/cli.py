"""Command-line interface for gitops-scaffold.

Three top-level commands, matching the three stages of the pipeline
described in ``docs/architecture.md``:

- ``analyze``:  parse + analyze, print a confidence report. No files written.
- ``generate``: parse + analyze + generate manifests to an output directory.
- ``validate``: check a previously generated output directory for structural
  issues (missing files, unresolved review markers).

``analyze`` and ``generate`` depend on a real parser being wired up, which is
the v0.2 milestone (see ``docs/roadmap.md``) — for now they exit non-zero
with a clear message rather than silently doing nothing. ``validate`` is
fully functional today since it only inspects the filesystem.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from gitops_scaffold import __version__
from gitops_scaffold.utils.logging import configure_logging
from gitops_scaffold.validators.structure import StructureValidator

app = typer.Typer(
    name="gitops-scaffold",
    help="Analyze application definitions and generate opinionated, production-ready GitOps manifests.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


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
        exists=True,
        help="Path to an application definition, e.g. docker-compose.yml",
    ),
) -> None:
    """Analyze an application definition and print a confidence report."""
    console.print(
        "[yellow]Analysis is not yet implemented.[/yellow] "
        "Docker Compose parsing lands in v0.2 — see docs/roadmap.md."
    )
    console.print(f"Source provided: [bold]{source}[/bold]")
    raise typer.Exit(code=1)


@app.command()
def generate(
    source: Path = typer.Argument(
        ...,
        exists=True,
        help="Path to an application definition, e.g. docker-compose.yml",
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
        "See docs/roadmap.md for the v0.2/v0.3 milestones."
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
