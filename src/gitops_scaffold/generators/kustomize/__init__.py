"""FluxCD + Kustomize manifest generators.

Plain Kubernetes manifests only — no Helm generation in the first release
(see ``docs/roadmap.md``). Each module below owns exactly one resource kind
and is currently a scaffolding placeholder pending v0.2/v0.3 implementation:

- ``deployment``: Deployment
- ``service``: Service
- ``configmap``: ConfigMap
- ``pvc``: PersistentVolumeClaim
- ``secret``: ``secret.example.yaml`` placeholder (never a real Secret)
- ``ingress``: Ingress
- ``kustomization``: ``kustomization.yaml``
- ``readme``: generated README describing the output
- ``checklist``: the validation checklist (``VALIDATION_CHECKLIST.md``)
"""

from __future__ import annotations
