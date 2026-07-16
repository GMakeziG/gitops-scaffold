"""Command-line interface for gitops-scaffold.

Three top-level commands, matching the three stages of the pipeline
described in ``docs/architecture.md``:

- ``analyze``:  parse + analyze, print a confidence report. No files written
  unless ``--output`` is given, in which case the full analysis is also
  saved as JSON — the same schema ``generate`` accepts as cached input.
- ``generate``: parse + analyze + generate manifests to an output directory.
  Accepts either a Compose file or a saved ``analyze --output`` report —
  both converge on the same ``GenerationPipeline`` (see ``generation_io.py``).
- ``validate``: check a previously generated output directory for structural
  and semantic issues.

Exit codes for both ``analyze`` and ``generate``: **1** means the input
couldn't be parsed/resolved at all (bad path, unrecognized format, malformed
Compose, malformed report, bad ``--ingress-*`` combination, or an
overwrite-safety block); **2** means the run completed but the underlying
analysis has at least one CRITICAL finding; **0** means it completed with
only INFO/WARNING findings (or none).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console

from gitops_scaffold import __version__
from gitops_scaffold.analyzer.default import DefaultAnalyzer
from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generation_io import plan_overwrite, resolve_input, write_generated_files
from gitops_scaffold.generators.ingress_config import IngressConfig
from gitops_scaffold.generators.pipeline import GenerationPipeline
from gitops_scaffold.models.generation_report import GenerationReport
from gitops_scaffold.models.report import AnalysisReport
from gitops_scaffold.parsers.base import ParserError
from gitops_scaffold.parsers.registry import detect_parser
from gitops_scaffold.reporting.report import Reporter, redact_application
from gitops_scaffold.utils.fs import write_file
from gitops_scaffold.utils.kubectl import try_kustomize_build
from gitops_scaffold.utils.logging import configure_logging
from gitops_scaffold.validators.manifests import ManifestConsistencyValidator
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
        help=(
            "Path to an application definition (e.g. docker-compose.yml) or a saved "
            "analysis report produced by 'analyze --output'."
        ),
    ),
    app_name: str | None = typer.Option(
        None, "--app", "-a", help="Override the application name used for labels and README."
    ),
    namespace: str | None = typer.Option(
        None, "--namespace", "-n", help="Override the configured default namespace."
    ),
    output: Path = typer.Option(
        Path("./gitops"), "--output", "-o", help="Directory to write generated manifests to."
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite files this tool previously generated in --output."
    ),
    ingress_host: str | None = typer.Option(
        None, "--ingress-host", help="Enable Ingress generation for this host."
    ),
    ingress_class: str | None = typer.Option(None, "--ingress-class"),
    tls_secret: str | None = typer.Option(None, "--tls-secret"),
    cluster_issuer: str | None = typer.Option(None, "--cluster-issuer"),
) -> None:
    """Generate GitOps manifests from an application definition or a saved report."""
    if not source.exists():
        console.print(f"[red]Error:[/red] {source} does not exist.")
        raise typer.Exit(code=1)

    settings = ScaffoldSettings.load(source.parent / ".gitops-scaffold.yaml")
    if namespace is not None:
        settings = settings.model_copy(update={"default_namespace": namespace})

    try:
        application, analysis = resolve_input(source, settings)
    except ParserError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if app_name is not None:
        application = application.model_copy(update={"name": app_name})

    ingress_flags = (ingress_host, ingress_class, tls_secret, cluster_issuer)
    ingress_config = None
    if any(ingress_flags):
        if not (ingress_host and ingress_class and tls_secret and cluster_issuer):
            console.print(
                "[red]Error:[/red] --ingress-host, --ingress-class, --tls-secret, and "
                "--cluster-issuer must all be given together."
            )
            raise typer.Exit(code=1)
        ingress_config = IngressConfig(
            host=ingress_host,
            ingress_class=ingress_class,
            tls_secret=tls_secret,
            cluster_issuer=cluster_issuer,
        )

    outcome = GenerationPipeline(settings, ingress_config).generate(application, analysis)

    this_run_paths = {str(f.relative_path) for f in outcome.files} | {"generation-report.json"}
    decision = plan_overwrite(output, this_run_paths)

    if decision.foreign:
        console.print(
            "[red]Error:[/red] refusing to overwrite files not managed by gitops-scaffold:"
        )
        for path in decision.foreign:
            console.print(f"  {path}")
        raise typer.Exit(code=1)

    # Report every blocking reason at once (not just the first one found) so
    # --force's effect is clear from a single run rather than discovered
    # incrementally across repeated invocations.
    blocked = False
    if decision.managed_conflicts and not force:
        blocked = True
        console.print("[red]Error:[/red] output already exists (re-run with --force to overwrite):")
        for path in decision.managed_conflicts:
            console.print(f"  {path}")
    if decision.orphaned and not force:
        blocked = True
        console.print(
            "[red]Error:[/red] the previous output here contains files this run no longer "
            "generates (re-run with --force to proceed — they will not be deleted):"
        )
        for path in decision.orphaned:
            console.print(f"  {path}")
    if blocked:
        raise typer.Exit(code=1)

    report = GenerationReport(
        generator_version=__version__,
        application_name=application.name,
        namespace=settings.default_namespace,
        confidence=analysis.confidence,
        generated_files=tuple(sorted(this_run_paths)),
        files_requiring_review=tuple(
            sorted(str(f.relative_path) for f in outcome.files if f.requires_review)
        ),
        notes=outcome.notes,
        overwritten_files=decision.managed_conflicts,
        orphaned_files=decision.orphaned if force else (),
        analysis=analysis,
    )

    write_generated_files(output, outcome.files, report)

    console.print(f"[green]Generated {len(outcome.files)} file(s) in {output}[/green]")
    if report.files_requiring_review:
        console.print(
            f"[yellow]{len(report.files_requiring_review)} file(s) need review[/yellow] — "
            "see README.md / generation-report.json"
        )
    if decision.orphaned:
        console.print(f"[yellow]{len(decision.orphaned)} orphaned file(s) left in place[/yellow]")

    if analysis.criticals:
        raise typer.Exit(code=2)
    raise typer.Exit(code=0)


@app.command()
def validate(
    output_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        help="Directory containing previously generated GitOps manifests.",
    ),
    use_kubectl: bool = typer.Option(
        False,
        "--kubectl",
        help="Also run 'kubectl kustomize' if kubectl is installed (never a hard dependency).",
    ),
) -> None:
    """Validate a generated GitOps output directory's structure and consistency."""
    findings = [
        *StructureValidator().validate(output_dir),
        *ManifestConsistencyValidator().validate(output_dir),
    ]

    for finding in findings:
        color = "red" if finding.severity.value == "critical" else "yellow"
        console.print(f"[{color}]{finding.severity.value.upper()}[/{color}] {finding.message}")

    if not findings:
        console.print(f"[green]No issues found in {output_dir}[/green]")

    if use_kubectl:
        result = try_kustomize_build(output_dir)
        if result is None:
            console.print("[dim]kubectl not found on PATH — skipped.[/dim]")
        elif result.succeeded:
            console.print("[green]kubectl kustomize succeeded.[/green]")
        else:
            console.print(f"[yellow]kubectl kustomize failed:[/yellow]\n{result.output}")

    if findings:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
