from __future__ import annotations

from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.models.generation_report import GenerationReport


def test_generation_outcome_defaults_to_empty() -> None:
    outcome = GenerationOutcome()
    assert outcome.files == ()
    assert outcome.notes == ()


def test_generation_note_requires_review_defaults_false() -> None:
    note = GenerationNote(category=GenerationNoteCategory.ASSUMPTION, message="m")
    assert note.requires_review is False
    assert note.service_name is None


def test_generated_file_requires_review_defaults_false() -> None:
    from pathlib import Path

    file = GeneratedFile(relative_path=Path("deployment.yaml"), content="x")
    assert file.requires_review is False


def test_generation_report_filters_notes_by_category() -> None:
    notes = (
        GenerationNote(
            category=GenerationNoteCategory.ASSUMPTION, message="a", requires_review=True
        ),
        GenerationNote(category=GenerationNoteCategory.SKIPPED, message="s"),
        GenerationNote(category=GenerationNoteCategory.WARNING, message="w"),
        GenerationNote(category=GenerationNoteCategory.ASSUMPTION, message="a2"),
    )
    report = GenerationReport(
        generator_version="0.1.0",
        application_name="demo",
        namespace="default",
        confidence=0.9,
        notes=notes,
        analysis=AnalysisResult(application_name="demo", confidence=0.9),
    )

    assert [n.message for n in report.assumptions] == ["a", "a2"]
    assert [n.message for n in report.skipped] == ["s"]
    assert [n.message for n in report.warnings] == ["w"]


def test_generation_report_never_embeds_application_definition() -> None:
    # A structural guarantee, not just a convention: GenerationReport has no
    # field capable of holding an ApplicationDefinition (and therefore no
    # EnvVar values) at all.
    assert "application" not in GenerationReport.model_fields
    assert set(GenerationReport.model_fields) >= {"application_name", "namespace"}
