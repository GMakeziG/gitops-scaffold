"""Validates the on-disk structure of a generated GitOps output directory.

This is the one validator that is fully implemented in v0.1: it only checks
that the expected files exist and that no generated manifest still contains
an unresolved ``TODO`` / ``REVIEW REQUIRED`` marker — it does not (yet)
validate Kubernetes API schema correctness.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.validators.base import Validator

#: Files every generated output directory is expected to contain.
#: ``secret.example.yaml`` is intentionally required: real secrets must never
#: be generated, but a placeholder documenting expected keys always should be.
EXPECTED_FILES: tuple[str, ...] = (
    "kustomization.yaml",
    "README.md",
    "VALIDATION_CHECKLIST.md",
    "secret.example.yaml",
)

#: Substrings that indicate a manifest still needs human review before it's
#: safe to apply.
REVIEW_MARKERS: tuple[str, ...] = ("TODO", "REVIEW REQUIRED")


class StructureValidator(Validator):
    """Checks that a generated output directory has the expected shape."""

    def validate(self, output_dir: Path) -> tuple[Finding, ...]:
        findings: list[Finding] = []

        for filename in EXPECTED_FILES:
            if not (output_dir / filename).is_file():
                findings.append(
                    Finding(
                        code="structure-missing-file",
                        message=f"Expected file '{filename}' was not found in {output_dir}.",
                        severity=Severity.CRITICAL,
                        remediation=f"Re-run 'gitops-scaffold generate' or create '{filename}' manually.",
                    )
                )

        for path in sorted(output_dir.rglob("*.yaml")):
            text = path.read_text(errors="ignore")
            for marker in REVIEW_MARKERS:
                if marker in text:
                    findings.append(
                        Finding(
                            code="structure-review-required",
                            message=f"{path.relative_to(output_dir)} still contains an unresolved '{marker}' marker.",
                            severity=Severity.WARNING,
                            remediation="Review and resolve the marked section before applying this manifest.",
                        )
                    )
                    break

        return tuple(findings)
