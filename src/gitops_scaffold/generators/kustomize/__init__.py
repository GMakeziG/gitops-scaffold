"""FluxCD + Kustomize manifest generators.

Plain Kubernetes manifests only — no Helm generation (see ``docs/roadmap.md``).
Each module below owns exactly one resource kind:

- ``deployment``: Deployment
- ``service``: Service
- ``configmap``: ConfigMap
- ``pvc``: PersistentVolumeClaim
- ``secret``: ``secret.example.yaml`` placeholder (never a real Secret)
- ``ingress``: Ingress (optional, off by default — see ``cli.py``)
- ``kustomization``: ``kustomization.yaml``
- ``readme``: generated README describing the output

"REVIEW REQUIRED" items surface via each ``GeneratedFile``/``GenerationNote``
and end up in the generated README and ``generation-report.json`` — there is
no separate validation-checklist file (removed after v0.1; see
``docs/roadmap.md`` for why).
"""

from __future__ import annotations
