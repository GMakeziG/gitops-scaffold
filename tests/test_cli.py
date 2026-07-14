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


def test_analyze_reports_not_yet_implemented(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    result = runner.invoke(app, ["analyze", str(compose_file)])

    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_generate_reports_not_yet_implemented(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    result = runner.invoke(app, ["generate", str(compose_file)])

    assert result.exit_code == 1
    assert "not yet implemented" in result.output


def test_validate_passes_on_a_complete_output_directory(tmp_path: Path) -> None:
    for filename in EXPECTED_FILES:
        (tmp_path / filename).write_text("ok\n")

    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 0
    assert "No structural issues" in result.output


def test_validate_fails_on_an_incomplete_output_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", str(tmp_path)])

    assert result.exit_code == 1
