"""Validators: sanity-check a generated GitOps output directory.

Unlike parsers/analyzers/generators, ``StructureValidator`` is a real,
working implementation from v0.1 onward — it only checks filesystem
structure, not Kubernetes semantics, so it doesn't depend on Docker Compose
parsing being implemented yet. Deeper validation (schema checks against the
Kubernetes OpenAPI spec, ``kubeconform``/``kustomize build`` integration) is
planned for a later milestone (``docs/roadmap.md``).
"""

from __future__ import annotations

from gitops_scaffold.validators.base import Validator
from gitops_scaffold.validators.structure import StructureValidator

__all__ = ["StructureValidator", "Validator"]
