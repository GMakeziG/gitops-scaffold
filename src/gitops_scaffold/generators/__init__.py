"""Generators: turn an :class:`ApplicationDefinition` + :class:`AnalysisResult`
into files on disk.

The first release only targets plain Kubernetes manifests laid out for
FluxCD + Kustomize (see ``docs/architecture.md``); Helm chart generation is
explicitly out of scope until a later milestone (``docs/roadmap.md``).

Every generator must honor the same rule as the analyzer: never guess. Where
the analysis couldn't determine a value with confidence, the generator emits
a ``TODO`` / ``REVIEW REQUIRED`` marker in the rendered manifest instead of a
plausible-looking default.
"""

from __future__ import annotations

from gitops_scaffold.generators.base import ManifestGenerator

__all__ = ["ManifestGenerator"]
