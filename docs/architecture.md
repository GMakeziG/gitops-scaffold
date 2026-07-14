# Architecture

`gitops-scaffold` is organized as a pipeline of independently testable stages,
connected by one normalized intermediate representation (IR). Every stage
only depends on the IR — never on any other stage's implementation details —
so new input formats, detection rules, or output targets can be added without
touching the rest of the system.

```
                    ┌──────────────┐
   docker-compose.yml│              │
   Helm chart (later)│   Parsers    │──▶ ApplicationDefinition (IR)
   Dockerfile (later) │              │
   GitHub repo (later)└──────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │   Analyzer   │──▶ AnalysisResult (findings + confidence)
                      │  + rules/    │
                      └──────────────┘
                         │         │
                         ▼         ▼
                ┌──────────────┐ ┌──────────────┐
                │  Generators  │ │  Reporting   │──▶ Rich console report
                │ (+ Jinja2    │ └──────────────┘
                │  templates)  │
                └──────────────┘
                       │
                       ▼
              Kustomize/Flux manifests on disk
                       │
                       ▼
                ┌──────────────┐
                │  Validators  │──▶ structural + (later) schema checks
                └──────────────┘
```

## The intermediate representation

`gitops_scaffold.models.app.ApplicationDefinition` (and its nested
`ServiceDefinition`, `PortMapping`, `EnvVar`, `VolumeMount`, `HealthCheck`,
`RuntimeUser`) is the single normalized shape every parser must produce.
Analyzers, generators, and validators never know or care whether the original
input was Docker Compose, a Helm chart, or a Dockerfile — they only see this
IR. This is what makes "future support for Helm, OCI images, Dockerfiles, and
GitHub repositories" (see `docs/roadmap.md`) an additive change rather than a
rewrite: a new parser just needs to produce an `ApplicationDefinition`.

## Parsers (`gitops_scaffold.parsers`)

A `Parser` implements `can_parse(path) -> bool` (used for auto-detection) and
`parse(path) -> ApplicationDefinition`. Parsers must never guess: if a value
can't be determined from the input, it's left `None`/empty rather than
defaulted, so the analyzer can surface the gap explicitly.

## Analyzer (`gitops_scaffold.analyzer`)

An `Analyzer` runs a set of narrowly-scoped `DetectionRule` implementations
(`analyzer/rules/`) — one per concern (ports, secrets, ConfigMap values,
volumes, health checks, runtime user, security risks, persistence) — over
each service, and aggregates their `Finding`s plus an overall confidence
score into an `AnalysisResult`. Each rule is a pure function of one
`ServiceDefinition`, with no shared state, which keeps them trivial to unit
test independently.

This is the layer that enforces the project's core promise: **the tool never
silently guesses.** Anything a rule can't determine confidently becomes a
`Finding` (`INFO` / `WARNING` / `CRITICAL`), which flows through to both the
human-readable report and, later, `TODO` / `REVIEW REQUIRED` markers in
generated manifests.

## Generators (`gitops_scaffold.generators`)

A `ManifestGenerator` takes an `ApplicationDefinition` + `AnalysisResult` and
produces zero or more `GeneratedFile`s, usually by rendering a Jinja2 template
from `gitops_scaffold/templates/`. Each generator owns exactly one resource
kind (Deployment, Service, ConfigMap, PVC, Secret example, Ingress,
Kustomization, README, validation checklist) — see
`gitops_scaffold/generators/kustomize/`.

Two hard rules apply to every generator:

1. **Never generate a real Kubernetes `Secret`.** `secret.example.yaml` is
   always a placeholder with `CHANGEME` values; real secrets are the
   operator's responsibility, managed through whatever secret manager
   (SealedSecrets, External Secrets Operator, SOPS) fits their cluster.
2. **Never fill in a value the analysis wasn't confident about.** Where
   information is missing, the rendered manifest gets a `TODO` or
   `REVIEW REQUIRED` comment instead of a plausible-looking default.

Helm chart generation is explicitly out of scope for the first release —
output is plain Kubernetes manifests laid out for FluxCD + Kustomize.

## Reporting (`gitops_scaffold.reporting`)

`Reporter` renders an `AnalysisResult` as a Rich console report: one line per
finding (✔ / ⚠ / ✖ by severity) plus an overall confidence percentage. It has
no knowledge of any specific input format — it just renders whatever
`AnalysisResult` it's given, so it needed no changes as analyzers evolve.

## Validators (`gitops_scaffold.validators`)

`StructureValidator` checks that a generated output directory has the
expected shape (all required files present, no unresolved review markers) —
this is fully implemented from v0.1 onward, since it only inspects the
filesystem. Deeper validation (Kubernetes OpenAPI schema checks,
`kustomize build` / `kubeconform` integration) is a later milestone.

## Configuration (`gitops_scaffold.config`)

`ScaffoldSettings` holds opinionated, overridable defaults (default
namespace, storage class, image pull policy, ingress class, Flux
reconciliation interval) that apply across all generated manifests for a
project, loaded from an optional `.gitops-scaffold.yaml`.

## CLI (`gitops_scaffold.cli`)

A thin Typer layer wiring the stages above to three commands: `analyze`,
`generate`, and `validate`. The CLI itself contains no business logic — it
only orchestrates parser → analyzer → reporter/generator → validator calls
and renders their results.
