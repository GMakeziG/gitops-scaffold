# gitops-scaffold

**An extensible GitOps scaffolding platform** — not a Docker Compose → Kubernetes
YAML converter.

`gitops-scaffold` analyzes an application definition, tells you exactly what
it did and didn't understand about it, and generates production-ready,
opinionated GitOps manifests for FluxCD + Kustomize. Where it isn't
confident, it says so — in the report and in the generated files — instead
of quietly guessing.

> **Status:** early alpha (v0.2). `analyze` works end-to-end against Docker
> Compose files today; manifest generation (`generate`) is still a stub —
> see [`docs/roadmap.md`](docs/roadmap.md).

## Why not just convert Compose to YAML?

Mechanical translation tools exist already, and they all share the same
flaw: they turn ambiguity into silent, wrong defaults. A Compose file
doesn't say what UID a container runs as, whether a volume needs to survive
a pod restart, or what an acceptable storage size is — a naive converter
invents an answer anyway, and that answer ends up in production.

`gitops-scaffold` is built around a different contract:

- **Never silently guess.** If something can't be inferred with confidence,
  the output says so explicitly — as a warning in the report and as a
  `TODO` / `REVIEW REQUIRED` comment in the manifest itself.
- **Never generate a real secret.** Detected credentials become a
  `secret.example.yaml` placeholder, never a Kubernetes `Secret` with real
  values baked in.
- **Report before you generate.** `analyze` gives you a confidence score and
  a checklist of what was and wasn't understood, before anything is written
  to disk.
- **Extensible by design.** Docker Compose is the first input format, not
  the only one. Parsers, detection rules, and generators are all separate,
  independently testable interfaces — see [`docs/architecture.md`](docs/architecture.md).

## Example report

Real output for a public [Audiobookshelf](https://github.com/advplyr/audiobookshelf)
`docker-compose.yml` (bind mounts, no healthcheck, no declared user):

```sh
$ gitops-scaffold analyze docker-compose.yml
```

```
╭─────────────── gitops-scaffold report: audiobookshelf-compose ───────────────╮
│ Service: audiobookshelf                                                      │
│   Image: ghcr.io/advplyr/audiobookshelf:v2.35.1                              │
│   Ports: 13378->80/TCP                                                       │
│   Environment: TZ=America/New_York                                          │
│   Volumes: ./audiobooks->/audiobooks, ./podcasts->/podcasts, ...            │
│   Health check: none                                                        │
│   Runtime user: unspecified                                                 │
│                                                                              │
│ ✔ Service 'audiobookshelf' image detected: ghcr.io/.../audiobookshelf:v2.35.1│
│ ⚠ bind-mounts host path './audiobooks' — host paths don't translate to K8s. │
│ ⚠ Service 'audiobookshelf' declares no health check.                        │
│ ⚠ Service 'audiobookshelf' declares no user — runs as the image's default.  │
│ ⚠ Compose field 'container_name' was read but is not yet modeled.           │
│                                                                              │
│ Confidence: 65%                                                              │
╰────────────────────────────────────────────────────────────────────────────╯
```

## Installation

Requires Python 3.13+.

```sh
pip install gitops-scaffold   # not yet published — see Development below
```

## Usage

```sh
gitops-scaffold analyze docker-compose.yml
gitops-scaffold analyze docker-compose.yml --format json
gitops-scaffold analyze docker-compose.yml --output report.json
gitops-scaffold generate docker-compose.yml --output ./gitops   # v0.3, still stubbed
gitops-scaffold validate ./gitops
```

`analyze` works end-to-end today: `--format table` (default) prints the
report above; `--format json` prints the same analysis as a stable,
machine-readable `AnalysisReport` envelope; `--output PATH` additionally
saves that JSON to disk regardless of `--format` — the schema `generate` is
expected to accept as cached input once v0.3 lands. Exit codes: `0` if
analysis completed with only informational/warning findings, `1` if the
input couldn't be parsed at all, `2` if it completed but found at least one
CRITICAL finding (a hardcoded secret, `privileged: true`, etc.).

`generate` is still a stub for v0.3. `validate` is fully functional today: it
checks that a generated output directory has the expected files and no
unresolved review markers.

See [`docs/compose-support.md`](docs/compose-support.md) for exactly which
Compose fields are understood, how ambiguous values are classified, and
current limitations.

## What gets generated

For each service, `gitops-scaffold generate` produces plain Kubernetes
manifests laid out for FluxCD's Kustomization controller (`kubectl apply -k`
also works):

| File | Purpose |
| --- | --- |
| `deployment.yaml` | The workload itself |
| `service.yaml` | Cluster-internal networking |
| `configmap.yaml` | Non-secret configuration |
| `pvc.yaml` | Persistent storage, where detected |
| `secret.example.yaml` | Placeholder documenting expected secret keys — **never real values** |
| `ingress.yaml` | External HTTP routing, where applicable |
| `kustomization.yaml` | Ties every resource above together |
| `README.md` | What was generated and how to apply it |
| `VALIDATION_CHECKLIST.md` | Every finding you should resolve before applying |

Helm chart generation is intentionally out of scope for the first release —
see [`docs/roadmap.md`](docs/roadmap.md) for why, and what's planned instead.

## Architecture

```
Parsers → ApplicationDefinition (IR) → Analyzer → AnalysisResult
                                             │
                              ┌──────────────┼──────────────┐
                              ▼                             ▼
                         Generators                    Reporting
                     (Jinja2 templates)              (Rich console)
                              │
                              ▼
                   Kustomize/Flux manifests
                              │
                              ▼
                         Validators
```

Full write-up, including why the IR boundary exists and what each layer is
and isn't responsible for: [`docs/architecture.md`](docs/architecture.md).

## Design principles

1. **Separation of concerns.** Parsing, analysis, generation, and validation
   are independent layers connected only by the `ApplicationDefinition` /
   `AnalysisResult` intermediate representations — never by shared mutable
   state or format-specific assumptions leaking across layers.
2. **Confidence over convenience.** Every analysis produces a confidence
   score. Low confidence is surfaced loudly, not smoothed over.
3. **GitOps-native output.** Generated manifests assume FluxCD + Kustomize
   from the start, not a generic Kubernetes dump that needs restructuring.
4. **Security by default.** No plaintext secrets, ever. Runtime user,
   privilege, and mount detection feed directly into security-relevant
   `securityContext` fields and warnings.
5. **Fully typed, fully tested.** The codebase is typed end-to-end (checked
   with [ty](https://github.com/astral-sh/ty)) and has unit tests from the
   very first commit — not bolted on later.

## Development

```sh
git clone https://github.com/06ninjatronics/gitops-scaffold.git
cd gitops-scaffold
python3.13 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
ruff format --check .
ty check
pytest
```

Or use the convenience script: `scripts/check.sh` runs all of the above.

## Roadmap

See [`docs/roadmap.md`](docs/roadmap.md) for the full v0.1 → v1.0 plan,
including Helm/Dockerfile/OCI-image/GitHub-repo input support, deeper
security analysis, and multi-environment Kustomize overlays.

## Contributing

This project is in early alpha and its interfaces (`Parser`, `Analyzer`,
`DetectionRule`, `ManifestGenerator`, `Validator`) are still settling. Issues
and discussion are welcome; see `docs/architecture.md` before proposing a new
parser or generator so new additions fit the existing seams.

## License

[MIT](LICENSE)
