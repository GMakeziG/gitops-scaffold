"""Scaffold-wide settings that influence generation but aren't per-service.

These are opinionated defaults, overridable via a ``.gitops-scaffold.yaml``
config file in the project being scaffolded (loaded with :meth:`ScaffoldSettings.load`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class ScaffoldSettings(BaseModel):
    """Opinionated, overridable defaults applied across all generated manifests."""

    default_namespace: str = "default"
    default_storage_class: str | None = None
    image_pull_policy: str = "IfNotPresent"
    ingress_class_name: str | None = None
    flux_kustomization_interval: str = "10m"

    @classmethod
    def load(cls, path: Path | None = None) -> ScaffoldSettings:
        """Load settings from a YAML file, falling back to defaults if absent."""
        if path is None or not path.exists():
            return cls()
        data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        return cls(**data)
