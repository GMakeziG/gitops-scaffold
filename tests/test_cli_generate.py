from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import yaml
from typer.testing import CliRunner

from gitops_scaffold.cli import app
from gitops_scaffold.models.generation_report import GenerationReport

runner = CliRunner()


def test_generate_exits_1_on_nonexistent_source(tmp_path: Path) -> None:
    result = runner.invoke(app, ["generate", str(tmp_path / "missing.yml")])
    assert result.exit_code == 1


def test_generate_exits_1_on_malformed_compose(compose_fixture: Callable[[str], Path]) -> None:
    result = runner.invoke(
        app, ["generate", str(compose_fixture("malformed/missing-services-key-compose.yml"))]
    )
    assert result.exit_code == 1


def test_generate_exits_0_for_clean_service(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0


def test_generate_exits_2_on_critical_finding(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-2-critical-compose.yml")),
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 2


def test_generate_direct_compose_and_report_produce_identical_manifests(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    source = compose_fixture("audiobookshelf-compose.yml")
    report_path = tmp_path / "report.json"
    analyze_result = runner.invoke(
        app, ["analyze", str(source), "--format", "json", "--output", str(report_path)]
    )
    assert analyze_result.exit_code == 0

    direct_dir = tmp_path / "direct"
    report_dir = tmp_path / "from-report"
    direct_result = runner.invoke(
        app,
        [
            "generate",
            str(source),
            "--app",
            "audiobookshelf",
            "--namespace",
            "apps",
            "--output",
            str(direct_dir),
        ],
    )
    report_result = runner.invoke(
        app,
        [
            "generate",
            str(report_path),
            "--app",
            "audiobookshelf",
            "--namespace",
            "apps",
            "--output",
            str(report_dir),
        ],
    )
    assert direct_result.exit_code == 0
    assert report_result.exit_code == 0

    for filename in (
        "deployment.yaml",
        "service.yaml",
        "configmap.yaml",
        "pvc.yaml",
        "kustomization.yaml",
    ):
        assert (direct_dir / filename).read_text() == (report_dir / filename).read_text()


def test_generate_app_and_namespace_overrides_applied(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--app",
            "audiobookshelf",
            "--namespace",
            "apps",
            "--output",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 0
    doc = yaml.safe_load((tmp_path / "out" / "deployment.yaml").read_text())
    assert doc["metadata"]["namespace"] == "apps"
    assert doc["metadata"]["labels"]["app.kubernetes.io/part-of"] == "audiobookshelf"


def test_generate_audiobookshelf_golden_shape(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--app",
            "audiobookshelf",
            "--namespace",
            "apps",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0

    deployment = yaml.safe_load((out / "deployment.yaml").read_text())
    assert deployment["metadata"]["labels"]["app.kubernetes.io/managed-by"] == "gitops-scaffold"
    assert deployment["spec"]["template"]["spec"]["containers"][0]["image"] == (
        "ghcr.io/advplyr/audiobookshelf:v2.35.1"
    )
    port = deployment["spec"]["template"]["spec"]["containers"][0]["ports"][0]
    assert port["containerPort"] == 80

    service = yaml.safe_load((out / "service.yaml").read_text())
    assert service["spec"]["ports"][0]["port"] == 80
    assert "13378" not in (out / "service.yaml").read_text()
    assert "3005" not in (out / "service.yaml").read_text()

    configmap = yaml.safe_load((out / "configmap.yaml").read_text())
    assert configmap["data"]["TZ"] == "America/New_York"

    pvcs = list(yaml.safe_load_all((out / "pvc.yaml").read_text()))
    targets = {pvc["metadata"]["labels"]["app.kubernetes.io/name"] for pvc in pvcs}
    assert targets == {"audiobookshelf"}
    assert len(pvcs) == 4

    assert not (out / "secret.example.yaml").exists()

    report = GenerationReport.model_validate_json((out / "generation-report.json").read_text())
    assert report.namespace == "apps"
    assert any("runtime user" in n.message for n in report.notes)
    assert any("storage" in n.message.lower() or "PVC" in n.message for n in report.notes)


def test_generate_overwrite_protection_blocks_second_run(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    source = compose_fixture("exit-code-0-warnings-only-compose.yml")
    first = runner.invoke(app, ["generate", str(source), "--output", str(out)])
    assert first.exit_code == 0
    second = runner.invoke(app, ["generate", str(source), "--output", str(out)])
    assert second.exit_code == 1
    assert "already exists" in second.output


def test_generate_force_overwrites_managed_files(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    source = compose_fixture("exit-code-0-warnings-only-compose.yml")
    runner.invoke(app, ["generate", str(source), "--output", str(out)])
    second = runner.invoke(app, ["generate", str(source), "--output", str(out), "--force"])
    assert second.exit_code == 0
    report = GenerationReport.model_validate_json((out / "generation-report.json").read_text())
    assert "deployment.yaml" in report.overwritten_files


def test_generate_refuses_foreign_files_even_with_force(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "README.md").write_text("# hand-written, not ours\n")
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(out),
            "--force",
        ],
    )
    assert result.exit_code == 1
    assert "not managed by gitops-scaffold" in result.output
    assert (out / "README.md").read_text() == "# hand-written, not ours\n"


def test_generate_orphan_detection_blocks_without_force(tmp_path: Path) -> None:
    multi_compose = tmp_path / "docker-compose.yml"
    multi_compose.write_text(
        yaml.safe_dump({"services": {"web": {"image": "x:1.0"}, "db": {"image": "postgres:16"}}})
    )
    out = tmp_path / "out"
    first = runner.invoke(app, ["generate", str(multi_compose), "--output", str(out)])
    assert first.exit_code == 0
    assert (out / "web" / "deployment.yaml").exists()

    single_compose = tmp_path / "docker-compose-single.yml"
    single_compose.write_text(yaml.safe_dump({"services": {"web": {"image": "x:1.0"}}}))
    # Regenerating into the same directory with only one service now leaves
    # db/* orphaned -- must block without --force.
    import shutil

    shutil.copy(single_compose, tmp_path / "docker-compose.yml")
    second = runner.invoke(
        app, ["generate", str(tmp_path / "docker-compose.yml"), "--output", str(out)]
    )
    assert second.exit_code == 1
    assert "no longer generates" in second.output


def test_generate_orphan_left_in_place_with_force(tmp_path: Path) -> None:
    import shutil

    multi_compose = tmp_path / "docker-compose.yml"
    multi_compose.write_text(
        yaml.safe_dump({"services": {"web": {"image": "x:1.0"}, "db": {"image": "postgres:16"}}})
    )
    out = tmp_path / "out"
    runner.invoke(app, ["generate", str(multi_compose), "--output", str(out)])

    single_compose = tmp_path / "docker-compose-single.yml"
    single_compose.write_text(yaml.safe_dump({"services": {"web": {"image": "x:1.0"}}}))
    shutil.copy(single_compose, multi_compose)

    result = runner.invoke(app, ["generate", str(multi_compose), "--output", str(out), "--force"])
    assert result.exit_code == 0
    # Orphaned db/ subdirectory is never deleted.
    assert (out / "db" / "deployment.yaml").exists()
    report = GenerationReport.model_validate_json((out / "generation-report.json").read_text())
    assert any("db" in path for path in report.orphaned_files)


def test_generate_malformed_report_json_exits_1(tmp_path: Path) -> None:
    bad_report = tmp_path / "report.json"
    bad_report.write_text('{"not": "a valid report"}')
    result = runner.invoke(app, ["generate", str(bad_report), "--output", str(tmp_path / "out")])
    assert result.exit_code == 1


def test_generate_ingress_requires_all_four_flags(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("exit-code-0-warnings-only-compose.yml")),
            "--output",
            str(tmp_path / "out"),
            "--ingress-host",
            "example.com",
        ],
    )
    assert result.exit_code == 1
    assert "must all be given together" in " ".join(result.output.split())


def test_generate_ingress_generated_when_all_flags_given(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "generate",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--app",
            "audiobookshelf",
            "--output",
            str(out),
            "--ingress-host",
            "audiobooks.example.com",
            "--ingress-class",
            "traefik",
            "--tls-secret",
            "audiobooks-tls",
            "--cluster-issuer",
            "letsencrypt-production",
        ],
    )
    assert result.exit_code == 0
    assert (out / "ingress.yaml").exists()
    doc = yaml.safe_load((out / "kustomization.yaml").read_text())
    assert "ingress.yaml" in doc["resources"]


def test_generate_never_writes_plaintext_secret(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        app, ["generate", str(compose_fixture("secrets-compose.yml")), "--output", str(out)]
    )
    for generated_file in out.rglob("*"):
        if generated_file.is_file():
            content = generated_file.read_text()
            assert "sk_live_hardcoded_literal_value_12345" not in content
            assert "***REDACTED***" not in content
    assert result.exit_code in (0, 2)


def test_generate_json_report_input_via_output_flag(
    compose_fixture: Callable[[str], Path], tmp_path: Path
) -> None:
    report_path = tmp_path / "report.json"
    runner.invoke(
        app,
        [
            "analyze",
            str(compose_fixture("audiobookshelf-compose.yml")),
            "--format",
            "json",
            "--output",
            str(report_path),
        ],
    )
    data = json.loads(report_path.read_text())
    assert data["schema_version"] == 1

    out = tmp_path / "out"
    result = runner.invoke(app, ["generate", str(report_path), "--output", str(out)])
    assert result.exit_code == 0
    assert (out / "deployment.yaml").exists()
