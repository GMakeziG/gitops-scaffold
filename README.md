# gitops-scaffold

**An extensible GitOps scaffolding platform** — not a Docker Compose → Kubernetes
YAML converter.

`gitops-scaffold` analyzes an application definition, tells you exactly what
it did and didn't understand about it, and generates production-ready,
opinionated GitOps manifests for FluxCD + Kustomize. Where it isn't
confident, it says so — in the report and in the generated files — instead
of quietly guessing.

> **Status:** early alpha (v0.1). This milestone is project scaffolding only:
> package layout, interfaces, and tooling. Docker Compose parsing itself
> lands in v0.2. See [`docs/roadmap.md`](docs/roadmap.md).

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

```
✔ Image detected
✔ Ports detected
✔ Volumes detected
⚠ Health endpoint unknown
⚠ UID/GID unknown
⚠ Storage size requires review

Confidence: 87%
```

## Installation

Requires Python 3.13+.

```sh
pip install gitops-scaffold   # not yet published — see Development below
```

## Usage

```sh
gitops-scaffold analyze docker-compose.yml
gitops-scaffold generate docker-compose.yml --output ./gitops
gitops-scaffold validate ./gitops
```

`analyze` and `generate` currently exit with a "not yet implemented" message
— Compose parsing is the v0.2 milestone. `validate` is fully functional
today: it checks that a generated output directory has the expected files
and no unresolved review markers.

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
