from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from typer.testing import CliRunner

from gitops_scaffold.cli import app
from gitops_scaffold.models.report import AnalysisReport

runner = CliRunner()


def test_analyze_exits_0_with_only_warnings(compose_fixture: Callable[[str], Path]) -> None:
    result = runner.invoke(
        app, ["analyze", str(compose_fixture("exit-code-0-warnings-only-compose.yml"))]
    )
    assert result.exit_code == 0


def test_analyze_exits_1_on_nonexistent_file(tmp_path: Path) -> None:
    result = runner.invoke(app, ["analyze", str(tmp_path / "missing.yml")])
    assert result.exit_code == 1


def test_analyze_exits_1_on_malformed_compose(compose_fixture: Callable[[str], Path]) -> None:
    result = runner.invoke(
        app, ["analyze", str(compose_fixture("malformed/missing-services-key-compose.yml"))]
    )
    assert result.exit_code == 1


def test_analyze_exits_2_on_critical_finding(compose_fixture: Callable[[str], Path]) -> None:
    result = runner.invoke(
        app, ["analyze", str(compose_fixture("exit-code-2-critical-compose.yml"))]
    )
    assert result.exit_code == 2


def test_analyze_json_format_round_trips(compose_fixture: Callable[[str], Path]) -> None:
    result = runner.invoke(
        app, ["analyze", str(compose_fixture("audiobookshelf-compose.yml")), "--format", "json"]
    )
    report = AnalysisReport.model_validate_json(result.output)
    assert report.application.services[0].image == "ghcr.io/advplyr/audiobookshelf:v2.35.1"
    assert report.schema_version == 1


def test_analyze_output_flag_writes_json_file(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    output_path = tmp_path / "report.json"
    result = runner.invoke(
        app,
        [
            "analyze",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--output",
            str(output_path),
        ],
    )
    assert result.exit_code == 0
    assert output_path.exists()

    report = AnalysisReport.model_validate_json(output_path.read_text())
    assert report.application.name

    # Re-running with --output must not fail on an already-existing file.
    result_again = runner.invoke(
        app,
        [
            "analyze",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--output",
            str(output_path),
        ],
    )
    assert result_again.exit_code == 0


def test_analyze_never_prints_literal_secret_value_table_format(
    compose_fixture: Callable[[str], Path],
) -> None:
    result = runner.invoke(app, ["analyze", str(compose_fixture("secrets-compose.yml"))])
    assert "sk_live_hardcoded_literal_value_12345" not in result.output


def test_analyze_never_prints_literal_secret_value_json_format(
    compose_fixture: Callable[[str], Path],
) -> None:
    result = runner.invoke(
        app, ["analyze", str(compose_fixture("secrets-compose.yml")), "--format", "json"]
    )
    assert "sk_live_hardcoded_literal_value_12345" not in result.output

    data = json.loads(result.output)
    assert data["schema_version"] == 1
    env_by_name = {
        var["name"]: var["value"] for var in data["application"]["services"][0]["environment"]
    }
    assert env_by_name["API_TOKEN"] == "***REDACTED***"
    # Analysis findings are computed from the real value beforehand, so the
    # classification itself is unaffected by output-time redaction.
    assert any(
        finding["code"] == "secret-literal-value" for finding in data["analysis"]["findings"]
    )
