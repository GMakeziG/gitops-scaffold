"""Scaffold-wide settings that influence generation but aren't per-service.

These are opinionated defaults, overridable via a ``.gitops-scaffold.yaml``
config file in the project being scaffolded (loaded with :meth:`ScaffoldSettings.load`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

#: Substrings matched case-insensitively against environment variable names
#: to flag them as likely secrets. See ``analyzer/rules/secrets.py``.
DEFAULT_SECRET_NAME_PATTERNS: tuple[str, ...] = (
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "SECRET",
    "API_KEY",
    "PRIVATE_KEY",
    "CLIENT_SECRET",
    "ACCESS_KEY",
)


class ScaffoldSettings(BaseModel):
    """Opinionated, overridable defaults applied across all generated manifests."""

    default_namespace: str = "default"
    default_storage_class: str | None = None
    image_pull_policy: str = "IfNotPresent"
    ingress_class_name: str | None = None
    flux_kustomization_interval: str = "10m"
    secret_name_patterns: tuple[str, ...] = DEFAULT_SECRET_NAME_PATTERNS

    #: Generated Service ``type``. See ``generators/kustomize/service.py``.
    service_type: str = "ClusterIP"

    #: Injected into the Deployment's ``resources`` block only when Compose
    #: didn't declare a value for that field *and* this is explicitly set —
    #: never invented, per ``docs/generation.md``.
    default_cpu_request: str | None = None
    default_cpu_limit: str | None = None
    default_memory_request: str | None = None
    default_memory_limit: str | None = None

    #: PVC defaults. Compose has no size concept at all, so the size is
    #: always marked REVIEW REQUIRED regardless of this default — see
    #: ``generators/kustomize/pvc.py``.
    default_pvc_size: str = "1Gi"
    default_access_mode: str = "ReadWriteOnce"

    #: Extra labels merged onto every generated resource's ``app.kubernetes.io``
    #: label set.
    additional_labels: dict[str, str] = Field(default_factory=dict)

    #: Compose healthcheck translation only ever generates a `readinessProbe`
    #: by default; set this to also add an identical `livenessProbe` — see
    #: ``generators/kustomize/deployment.py``.
    enable_liveness_probe: bool = False

    #: Documented escape hatch for overriding which container port a named
    #: service treats as primary. Only applied when that service has exactly
    #: one port (ignored, with a note, otherwise). Empty by default — never
    #: populated automatically for any built-in fixture.
    port_overrides: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> ScaffoldSettings:
        """Load settings from a YAML file, falling back to defaults if absent."""
        if path is None or not path.exists():
            return cls()
        data: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
        return cls(**data)
