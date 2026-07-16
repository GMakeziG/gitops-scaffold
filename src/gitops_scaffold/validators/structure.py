"""Validates the on-disk structure of a generated GitOps output directory.

Checks that the always-required files exist and that no generated manifest
still contains an unresolved ``TODO`` / ``REVIEW REQUIRED`` marker. Does
**not** check semantic correctness (Service/Deployment/PVC cross-references,
resource name validity, ...) — see
:class:`~gitops_scaffold.validators.manifests.ManifestConsistencyValidator`
for that.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.validators.base import Validator

#: Files every generated output directory is always expected to contain.
#: ``secret.example.yaml`` is deliberately **not** here — it's conditional
#: (only generated when secret-shaped variables were detected), so a
#: validator with no other information shouldn't fail over something it
#: can't know is required.
EXPECTED_FILES: tuple[str, ...] = (
    "kustomization.yaml",
    "README.md",
    "generation-report.json",
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
