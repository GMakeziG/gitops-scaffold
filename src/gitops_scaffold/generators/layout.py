"""The shared directory-layout decision: flat for a single service, one
subdirectory per service otherwise.

A single-service application (the common case — one Compose service, e.g.
Audiobookshelf) gets the exact flat structure: ``configmap.yaml``,
``deployment.yaml``, etc. directly under the output directory. An
application with more than one service gets one kebab-cased subdirectory per
service, each with its own manifests and its own ``kustomization.yaml``; a
root ``kustomization.yaml``/``README.md``/``generation-report.json`` (and any
shared-named-volume PVC — see ``generators/volumes.py``) live at the output
root regardless. See ``docs/generation.md``.
"""

from __future__ import annotations

from pathlib import Path

from gitops_scaffold.utils.naming import kebab_case


def is_multi_service(total_services: int) -> bool:
    return total_services > 1


def resource_path(service_name: str, filename: str, total_services: int) -> Path:
    """The relative path one service's generated file should be written to."""
    if is_multi_service(total_services):
        return Path(kebab_case(service_name)) / filename
    return Path(filename)
