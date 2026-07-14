"""The validator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from gitops_scaffold.models.analysis import Finding


class Validator(ABC):
    """Base interface for validating a generated GitOps output directory."""

    @abstractmethod
    def validate(self, output_dir: Path) -> tuple[Finding, ...]:
        """Return findings describing problems with ``output_dir``.

        An empty tuple means validation passed.
        """
        raise NotImplementedError
