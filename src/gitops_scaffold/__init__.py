"""gitops-scaffold: an extensible GitOps scaffolding platform.

This package analyzes application definitions (Docker Compose today; Helm,
Dockerfiles, and OCI images in future milestones) and generates
production-ready, opinionated GitOps manifests for FluxCD + Kustomize.

See docs/architecture.md for the layered design and docs/roadmap.md for
where this project is headed.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
