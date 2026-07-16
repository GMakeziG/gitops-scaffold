"""Derives which environment variables are secret-shaped, from analysis
findings only — never by re-running ``looks_like_secret`` at generation time.

This matters concretely: ``generate report.json`` receives an
``ApplicationDefinition`` whose secret-shaped ``EnvVar.value``s are already
``"***REDACTED***"`` (``analyze --output`` redacts before writing). If
generation re-ran ``looks_like_secret`` with its own local
``.gitops-scaffold.yaml`` (which might configure different patterns than
whatever produced the report), a variable the original analysis called
secret could fail to be recognized, and the redaction marker itself could
leak into a ConfigMap as if it were a real value. Deriving the classification
from ``AnalysisResult.findings`` instead makes it fully determined by
whatever analysis already happened — identical whether that analysis is
embedded in a cached report or freshly computed from Compose in the same
process, since both converge on one ``AnalysisResult`` before generation
ever runs (see ``cli.py``'s input resolution).
"""

from __future__ import annotations

from gitops_scaffold.models.analysis import AnalysisResult

#: Finding codes produced by ``analyzer/rules/secrets.py`` for a variable
#: that has a value at all in the file (as opposed to being sourced from the
#: shell environment). See :func:`is_optional`.
_REQUIRED_SECRET_CODES = frozenset({"secret-literal-value", "secret-interpolated", "secret-empty"})
_OPTIONAL_SECRET_CODE = "secret-shell-passthrough"
_SECRET_CODES = _REQUIRED_SECRET_CODES | {_OPTIONAL_SECRET_CODE}

_ENV_FIELD_PREFIX = "environment."


def secret_classifications(service_name: str, analysis: AnalysisResult) -> dict[str, str]:
    """Returns ``{var_name: finding_code}`` for every secret-shaped variable of ``service_name``.

    Excludes ``secret-env-file-reference`` findings — those describe a
    service-level ``env_file:`` reference, not a specific variable, and
    never appear in ``service.environment`` in the first place.
    """
    classifications: dict[str, str] = {}
    for finding in analysis.findings:
        if finding.service_name != service_name:
            continue
        if finding.code not in _SECRET_CODES:
            continue
        if not finding.field_path or not finding.field_path.startswith(_ENV_FIELD_PREFIX):
            continue
        var_name = finding.field_path.removeprefix(_ENV_FIELD_PREFIX)
        classifications[var_name] = finding.code
    return classifications


def is_optional(finding_code: str) -> bool:
    """Whether a secret-classified variable should be ``optional: true`` on a ``secretKeyRef``.

    Only variables sourced entirely from the shell environment running
    Compose (no value written in the file at all) are treated as optional —
    Compose's closest equivalent to "this might not be set." A literal
    value, an interpolation, or an explicit empty string are all treated as
    required (Kubernetes' own default), since a value was clearly expected
    in some form.
    """
    return finding_code == _OPTIONAL_SECRET_CODE


def has_env_file_reference(service_name: str, analysis: AnalysisResult) -> bool:
    """Whether ``service_name`` declared an ``env_file:`` (contents never inspected)."""
    return any(
        finding.service_name == service_name and finding.code == "secret-env-file-reference"
        for finding in analysis.findings
    )
