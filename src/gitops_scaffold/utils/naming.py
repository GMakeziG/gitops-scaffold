"""Deterministic, Kubernetes-safe resource naming.

Used by every generator so PVC/ConfigMap/Secret/Deployment/Service names are
pure, collision-checkable functions of their inputs — never random, never
order-dependent.
"""

from __future__ import annotations

import hashlib
import re

#: Generic Kubernetes object name limit (RFC 1123 DNS subdomain).
MAX_RESOURCE_NAME_LENGTH = 253

#: Kubernetes port names (``containerPort.name`` / Service port `name`) must
#: additionally fit the much shorter IANA_SVC_NAME rules.
MAX_PORT_NAME_LENGTH = 15

_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
_REPEATED_HYPHENS = re.compile(r"-{2,}")


def kebab_case(text: str) -> str:
    """Lowercase, hyphenate, and strip ``text`` into a DNS-label-safe fragment."""
    text = text.strip().lower()
    text = re.sub(r"[/_\s]+", "-", text)
    text = _INVALID_CHARS.sub("-", text)
    text = _REPEATED_HYPHENS.sub("-", text).strip("-")
    return text or "unnamed"


def k8s_resource_name(*parts: str, max_length: int = MAX_RESOURCE_NAME_LENGTH) -> str:
    """Joins ``parts`` with ``-`` into a single kebab-cased, length-safe name.

    Truncation appends a short, deterministic hash of the full untruncated
    name rather than just chopping it off, so two different over-long names
    that happen to share a long common prefix don't collide after truncation.
    """
    joined = "-".join(kebab_case(p) for p in parts if p)
    name = kebab_case(joined)
    if len(name) <= max_length:
        return name
    digest = hashlib.sha1(name.encode()).hexdigest()[:8]
    return f"{name[: max_length - len(digest) - 1]}-{digest}"


def find_collisions(names: list[str]) -> dict[str, list[int]]:
    """Groups the indices of ``names`` by value, for values that appear more than once.

    Used to detect when two structurally different inputs (e.g. two
    differently-spelled service names) happen to kebab-case to the same
    resource name — a real, if rare, correctness hazard since two generated
    manifests would silently collide on disk otherwise.
    """
    by_name: dict[str, list[int]] = {}
    for index, name in enumerate(names):
        by_name.setdefault(name, []).append(index)
    return {name: indices for name, indices in by_name.items() if len(indices) > 1}
