"""Individual detection rules, one concern per module.

Each rule inspects a single :class:`~gitops_scaffold.models.app.ServiceDefinition`
and returns zero or more :class:`~gitops_scaffold.models.analysis.Finding`
instances. A concrete :class:`~gitops_scaffold.analyzer.base.Analyzer`
implementation composes these rules; no rule module talks to another.

Modules (all currently scaffolding placeholders — see ``docs/roadmap.md``):

- ``ports``: exposed port detection.
- ``secrets``: environment variables that look like credentials.
- ``configmap``: environment variables suitable for a ConfigMap.
- ``volumes``: volume mounts and whether they imply persistence.
- ``health``: presence/absence of a usable health check.
- ``runtime_user``: the UID/GID a container runs as.
- ``security``: broader security risks (privileged mode, host mounts, ...).
- ``persistence``: whether a service needs a PersistentVolumeClaim.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule

__all__ = ["DetectionRule"]
