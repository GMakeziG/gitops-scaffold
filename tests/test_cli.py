from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from gitops_scaffold import __version__
from gitops_scaffold.cli import app
from gitops_scaffold.validators.structure import EXPECTED_FILES

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_generate_exits_2_when_no_services_defined(tmp_path: Path) -> None:
    # An empty services block is a CRITICAL analysis finding ("no services
    # defined"), not an input/parse error -- generate still runs (producing a
    # near-empty output) but signals via exit code 2. See test_cli_generate.py
    # for the rest of `generate`'s real behavior.
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    result = runner.invoke(app, ["generate", str(compose_file), "--output", str(tmp_path / "out")])

    assert result.exit_code == 2


def test_validate_passes_on_a_complete_output_directory(tmp_path: Path) -> None:
    for filename in EXPECTED_FILES:
        (tmp_path / filename).write_text("ok\n")
    # kustomization.yaml is the one EXPECTED_FILES entry ManifestConsistencyValidator
    # also parses semantically -- give it minimally valid content instead of
    # the "ok\n" placeholder the other (non-YAML) expected files use.
    (tmp_path / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources: []\n"
    )

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "No issues found" in result.output


def test_validate_fails_on_an_incomplete_output_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 1
