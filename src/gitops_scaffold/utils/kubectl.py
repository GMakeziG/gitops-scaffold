"""Optional ``kubectl kustomize`` integration for ``validate --kubectl``.

``kubectl`` is never a hard dependency — if it isn't on ``PATH``, callers
should treat a ``None`` result as "skipped", never as a failure.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KubectlBuildResult:
    succeeded: bool
    output: str


def try_kustomize_build(directory: Path) -> KubectlBuildResult | None:
    """Runs ``kubectl kustomize <directory>``, or ``None`` if kubectl isn't installed."""
    kubectl = shutil.which("kubectl")
    if kubectl is None:
        return None
    try:
        result = subprocess.run(
            [kubectl, "kustomize", str(directory)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return KubectlBuildResult(succeeded=False, output=str(exc))
    if result.returncode == 0:
        return KubectlBuildResult(succeeded=True, output=result.stdout)
    return KubectlBuildResult(succeeded=False, output=result.stderr)
