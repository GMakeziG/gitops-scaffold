from __future__ import annotations

from pathlib import Path

from gitops_scaffold.validators.structure import EXPECTED_FILES, StructureValidator


def test_reports_critical_finding_for_each_missing_file(tmp_path: Path) -> None:
    findings = StructureValidator().validate(tmp_path)

    missing_codes = [f.code for f in findings]
    assert missing_codes.count("structure-missing-file") == len(EXPECTED_FILES)
    assert all(f.severity.value == "critical" for f in findings)


def test_passes_when_all_expected_files_exist(tmp_path: Path) -> None:
    for filename in EXPECTED_FILES:
        (tmp_path / filename).write_text("ok\n")

    findings = StructureValidator().validate(tmp_path)

    assert findings == ()


def test_flags_unresolved_review_markers(tmp_path: Path) -> None:
    for filename in EXPECTED_FILES:
        (tmp_path / filename).write_text("ok\n")
    (tmp_path / "deployment.yaml").write_text("# TODO: fill this in\n")

    findings = StructureValidator().validate(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "structure-review-required"
    assert findings[0].severity.value == "warning"
