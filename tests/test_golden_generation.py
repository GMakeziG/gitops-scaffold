"""Golden-file tests: exact generated output trees for two representative
fixtures (Audiobookshelf — the flagship single-service worked example —
and multi-service, which exercises the subdirectory layout, per-service
kustomizations, and a service-scoped secret.example.yaml). Only two of the
several scenarios get a full tree diff, matching v0.2's "representative
subset, not every fixture" precedent for golden-file maintenance — the rest
(app-with-secrets, multi-port, persistent-volume) are covered by targeted
assertions in test_cli_generate.py, test_generation_pipeline.py, and each
generator's own test module.
"""

from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from gitops_scaffold.cli import app

runner = CliRunner()

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "generated"
_COMPOSE_DIR = Path(__file__).parent / "fixtures" / "compose"


def _generate(compose_filename: str, app_name: str, output: Path) -> None:
    result = runner.invoke(
        app,
        [
            "generate",
            str(_COMPOSE_DIR / compose_filename),
            "--app",
            app_name,
            "--namespace",
            "apps",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code in (0, 2), result.output


def _normalize(relative: Path, text: str) -> str:
    # README.md's "from `<source path>`" line reflects whatever path string
    # the CLI was invoked with (relative in the checked-in golden tree,
    # absolute when pytest resolves fixtures under tmp_path) -- it's
    # invocation-dependent, not semantically meaningful content, so it's
    # normalized away rather than forced to match verbatim (mirroring how
    # v0.2's golden JSON tests normalize `source_path` for the same reason).
    if relative.name == "README.md":
        return re.sub(r"^from `.*`\.$", "from `<source>`.", text, flags=re.MULTILINE)
    return text


def _compare_trees(golden: Path, actual: Path) -> None:
    golden_files = {p.relative_to(golden) for p in golden.rglob("*") if p.is_file()}
    actual_files = {p.relative_to(actual) for p in actual.rglob("*") if p.is_file()}
    assert golden_files == actual_files, (
        f"file set mismatch\n  missing: {golden_files - actual_files}\n"
        f"  unexpected: {actual_files - golden_files}"
    )
    for relative in sorted(golden_files):
        expected = _normalize(relative, (golden / relative).read_text())
        got = _normalize(relative, (actual / relative).read_text())
        assert got == expected, f"content mismatch in {relative}"


def test_audiobookshelf_golden_tree(tmp_path: Path) -> None:
    output = tmp_path / "out"
    _generate("audiobookshelf-compose.yml", "audiobookshelf", output)
    _compare_trees(_GOLDEN_DIR / "audiobookshelf", output)


def test_multi_service_golden_tree(tmp_path: Path) -> None:
    output = tmp_path / "out"
    _generate("multi-service-compose.yml", "multiservice", output)
    _compare_trees(_GOLDEN_DIR / "multi-service", output)


def test_generation_is_deterministic_across_runs(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _generate("audiobookshelf-compose.yml", "audiobookshelf", first)
    _generate("audiobookshelf-compose.yml", "audiobookshelf", second)
    _compare_trees(first, second)
