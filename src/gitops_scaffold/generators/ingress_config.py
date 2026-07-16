"""Ingress is opt-in via CLI flags only (never a persisted config default) —
see ``cli.py``. This tiny value object is threaded into
:class:`~gitops_scaffold.generators.kustomize.ingress.IngressGenerator` and
:class:`~gitops_scaffold.generators.kustomize.kustomization.KustomizationGenerator`
only when all four flags are supplied together.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngressConfig:
    host: str
    ingress_class: str
    tls_secret: str
    cluster_issuer: str
