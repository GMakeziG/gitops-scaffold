"""Individual detection rules, one concern per module.

Each rule inspects a single :class:`~gitops_scaffold.models.app.ServiceDefinition`
and returns zero or more :class:`~gitops_scaffold.models.analysis.Finding`
instances. :class:`~gitops_scaffold.analyzer.default.DefaultAnalyzer` composes
these rules; no rule module talks to another (except ``configmap.py``, which
reuses ``secrets.py``'s ``looks_like_secret`` predicate as the single source
of truth for what counts as secret-shaped).

Modules:

- ``ports``: exposed port detection.
- ``secrets``: environment variables that look like credentials.
- ``configmap``: environment variables suitable for a ConfigMap.
- ``volumes``: volume mounts and whether they imply persistence.
- ``health``: presence/absence of a usable health check.
- ``runtime_user``: the UID/GID a container runs as.
- ``security``: broader security risks (privileged mode, host networking).
- ``persistence``: whether a service needs a PersistentVolumeClaim.
- ``image``: image reference hygiene (missing/unpinned/``:latest``).
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.analyzer.rules.configmap import ConfigMapDetectionRule
from gitops_scaffold.analyzer.rules.health import HealthCheckDetectionRule
from gitops_scaffold.analyzer.rules.image import ImageTagDetectionRule
from gitops_scaffold.analyzer.rules.persistence import PersistenceDetectionRule
from gitops_scaffold.analyzer.rules.ports import PortDetectionRule
from gitops_scaffold.analyzer.rules.runtime_user import RuntimeUserDetectionRule
from gitops_scaffold.analyzer.rules.secrets import SecretDetectionRule, looks_like_secret
from gitops_scaffold.analyzer.rules.security import SecurityRiskDetectionRule
from gitops_scaffold.analyzer.rules.volumes import VolumeDetectionRule

__all__ = [
    "ConfigMapDetectionRule",
    "DetectionRule",
    "HealthCheckDetectionRule",
    "ImageTagDetectionRule",
    "PersistenceDetectionRule",
    "PortDetectionRule",
    "RuntimeUserDetectionRule",
    "SecretDetectionRule",
    "SecurityRiskDetectionRule",
    "VolumeDetectionRule",
    "looks_like_secret",
]
