from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gitops_scaffold.cli import app
from gitops_scaffold.utils.kubectl import try_kustomize_build

runner = CliRunner()


def test_try_kustomize_build_returns_none_when_kubectl_missing(tmp_path: Path) -> None:
    with patch("shutil.which", return_value=None):
        assert try_kustomize_build(tmp_path) is None


def test_try_kustomize_build_reports_success(tmp_path: Path) -> None:
    (tmp_path / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources: []\n"
    )
    with (
        patch("shutil.which", return_value="/usr/bin/kubectl"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "---\n"
        result = try_kustomize_build(tmp_path)
    assert result is not None
    assert result.succeeded is True


def test_try_kustomize_build_reports_failure(tmp_path: Path) -> None:
    with (
        patch("shutil.which", return_value="/usr/bin/kubectl"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "boom"
        result = try_kustomize_build(tmp_path)
    assert result is not None
    assert result.succeeded is False
    assert "boom" in result.output


def test_validate_kubectl_flag_skips_gracefully_when_not_installed(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(out),
        ],
    )

    with patch("gitops_scaffold.cli.try_kustomize_build", return_value=None):
        result = runner.invoke(app, ["validate", str(out), "--kubectl"])
    assert "not found on PATH" in result.output


def test_validate_kubectl_flag_reports_success(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    from gitops_scaffold.utils.kubectl import KubectlBuildResult

    out = tmp_path / "out"
    runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(out),
        ],
    )

    with patch(
        "gitops_scaffold.cli.try_kustomize_build",
        return_value=KubectlBuildResult(succeeded=True, output="---\n"),
    ):
        result = runner.invoke(app, ["validate", str(out), "--kubectl"])
    assert "kubectl kustomize succeeded" in result.output


def test_validate_without_kubectl_flag_never_invokes_it(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(out),
        ],
    )

    with patch("gitops_scaffold.cli.try_kustomize_build") as mock_build:
        runner.invoke(app, ["validate", str(out)])
    mock_build.assert_not_called()
