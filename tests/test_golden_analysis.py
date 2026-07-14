"""Golden-file tests: exact `AnalysisReport` JSON for a few representative fixtures.

Only 3 of the 9+ Compose fixtures get a golden diff (audiobookshelf,
multi_service, secrets) to keep golden-file maintenance proportionate; the
rest are covered by targeted assertions in test_parsers.py/test_rules.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gitops_scaffold.analyzer.default import DefaultAnalyzer
from gitops_scaffold.models.report import AnalysisReport
from gitops_scaffold.parsers.compose import ComposeParser

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


def _generate_report(compose_filename: str) -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "compose" / compose_filename
    application = ComposeParser().parse(path)
    # Golden files are portable across machines/checkouts -- normalize away
    # the absolute source path before comparing.
    application = application.model_copy(update={"source_path": compose_filename})
    result = DefaultAnalyzer().analyze(application)
    report = AnalysisReport(application=application, analysis=result)
    return report.model_dump(mode="json")


@pytest.mark.parametrize(
    ("golden_name", "compose_filename"),
    [
        ("audiobookshelf", "audiobookshelf-compose.yml"),
        ("multi_service", "multi-service-compose.yml"),
        ("secrets", "secrets-compose.yml"),
    ],
)
def test_analysis_report_matches_golden_file(golden_name: str, compose_filename: str) -> None:
    actual = _generate_report(compose_filename)
    expected = json.loads((_GOLDEN_DIR / f"{golden_name}.json").read_text())
    assert actual == expected


def test_audiobookshelf_golden_has_zero_persistence_findings() -> None:
    expected = json.loads((_GOLDEN_DIR / "audiobookshelf.json").read_text())
    persistence_findings = [
        f for f in expected["analysis"]["findings"] if f["code"].startswith("persistence")
    ]
    assert persistence_findings == []
