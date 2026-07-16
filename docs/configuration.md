# Configuration

`gitops-scaffold` reads an optional `.gitops-scaffold.yaml` from the same
directory as the input file (Compose file or report) passed to `analyze` or
`generate`. Every field is optional; anything not set uses the documented
default. CLI flags (`--namespace`, etc.) override whatever this file
configures for that one run.

```yaml
# .gitops-scaffold.yaml
default_namespace: apps
secret_name_patterns:
  - PASSWORD
  - TOKEN
  - MY_CUSTOM_CRED_PATTERN
service_type: ClusterIP
default_cpu_request: "100m"
default_cpu_limit: "500m"
default_memory_request: "128Mi"
default_memory_limit: "512Mi"
default_pvc_size: "5Gi"
default_access_mode: ReadWriteOnce
additional_labels:
  team: platform
enable_liveness_probe: false
port_overrides:
  audiobookshelf: 3005
```

## Fields

| Field | Default | Used by |
| --- | --- | --- |
| `default_namespace` | `"default"` | every generator; overridden by `generate --namespace` |
| `default_storage_class` | `None` | reserved (not yet wired into PVC generation) |
| `image_pull_policy` | `"IfNotPresent"` | Deployment `imagePullPolicy` |
| `ingress_class_name` | `None` | reserved (Ingress class is set via `--ingress-class` instead — see below) |
| `flux_kustomization_interval` | `"10m"` | reserved for future Flux `Kustomization` object generation |
| `secret_name_patterns` | `PASSWORD, PASSWD, TOKEN, SECRET, API_KEY, PRIVATE_KEY, CLIENT_SECRET, ACCESS_KEY` | `analyzer/rules/secrets.py`'s `looks_like_secret` — matched case-insensitively as a substring of the variable name |
| `service_type` | `"ClusterIP"` | generated Service's `spec.type` |
| `default_cpu_request` / `default_cpu_limit` | `None` | Deployment `resources`, only when Compose declared nothing for that field |
| `default_memory_request` / `default_memory_limit` | `None` | same, for memory |
| `default_pvc_size` | `"1Gi"` | every generated PVC — always marked `REVIEW REQUIRED` regardless, since Compose has no size concept |
| `default_access_mode` | `"ReadWriteOnce"` | every generated PVC's `accessModes` |
| `additional_labels` | `{}` | merged onto every generated resource's labels (never onto Service/Deployment *selectors* — see `docs/generation.md`) |
| `enable_liveness_probe` | `false` | when `true`, also generates a `livenessProbe` identical to the `readinessProbe` (off by default — see `docs/generation.md`'s healthcheck section) |
| `port_overrides` | `{}` | keyed by service name; overrides which container port is treated as primary — **only applied when that service has exactly one port** (ignored, with a note, otherwise). Never populated automatically for any built-in fixture. |

## Ingress flags (CLI-only, not in `.gitops-scaffold.yaml`)

Ingress is opt-in per invocation, not a persisted default — see
`docs/generation.md`'s Ingress section:

```sh
gitops-scaffold generate docker-compose.yml \
  --ingress-host audiobooks.example.com \
  --ingress-class traefik \
  --tls-secret audiobooks-tls \
  --cluster-issuer letsencrypt-production
```

All four must be given together, or none at all.
