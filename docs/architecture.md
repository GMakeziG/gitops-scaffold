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
`RuntimeUser`, `ResourceRequirements`) is the single normalized shape every
parser must produce. Analyzers, generators, and validators never know or
care whether the original input was Docker Compose, a Helm chart, or a
Dockerfile — they only see this IR. This is what makes "future support for
Helm, OCI images, Dockerfiles, and GitHub repositories" (see
`docs/roadmap.md`) an additive change rather than a rewrite: a new parser
just needs to produce an `ApplicationDefinition`.

Anything a parser reads but doesn't model becomes a dotted-path string in
`unsupported_fields` (on both `ServiceDefinition` and `ApplicationDefinition`)
rather than being silently dropped — see `docs/compose-support.md` for the
full policy and field table. `Finding.field_path` closes the loop: it points
back to the exact dotted path a finding is about (e.g.
`environment.API_TOKEN`, `ports[0]`), relative to `Finding.service_name`.

## Parsers (`gitops_scaffold.parsers`)

A `Parser` implements `can_parse(path) -> bool` (used for auto-detection) and
`parse(path) -> ApplicationDefinition`. Parsers must never guess: if a value
can't be determined from the input, it's left `None`/empty rather than
defaulted, so the analyzer can surface the gap explicitly. Parsers only ever
answer "what does this file structurally declare?" — value judgments belong
entirely to the analyzer, never the parser.

`gitops_scaffold.parsers.registry.detect_parser(path)` tries every registered
`Parser` (`PARSERS`) in order and returns the first match, raising
`ParserError` if none apply. `ComposeParser` is the only fully implemented
parser as of v0.2; `DockerfileParser`, `HelmParser`, `KubernetesParser`, and
`GitHubRepositoryParser` are scaffolding placeholders (real `can_parse`,
`parse` raises `NotImplementedError`) so adding a real implementation later
never requires touching the CLI — only the registry and the new module.

## Analyzer (`gitops_scaffold.analyzer`)

`DefaultAnalyzer` runs a set of narrowly-scoped `DetectionRule`
implementations (`analyzer/rules/`) — one per concern (ports, secrets,
ConfigMap values, volumes, health checks, runtime user, security risks,
persistence, image tag hygiene) — over each service, and aggregates their
`Finding`s plus an overall confidence score into an `AnalysisResult`. Each
rule is a pure function of one `ServiceDefinition`, with no shared state,
which keeps them trivial to unit test independently.

Checks that need to see the *whole* application rather than one service
(cross-service host-port collisions, "no services defined") live directly in
`DefaultAnalyzer`, not in a `DetectionRule` — the rule interface stays
single-service-scoped on purpose. `DefaultAnalyzer` also converts
`unsupported_fields` into WARNING findings and computes confidence via
`analyzer/scoring.py` (see `docs/compose-support.md` for the exact formula).

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

`Reporter.render(app, result)` prints an inventory (services, images, ports,
environment variables, volumes, health checks, runtime user, dependencies) —
read directly from the `ApplicationDefinition` IR, since `AnalysisResult`
only ever holds findings and a confidence score by design — followed by one
line per finding (✔ / ⚠ / ✖ by severity) and the overall confidence
percentage. Environment variable values are redacted using
`analyzer.rules.secrets.looks_like_secret`, the same predicate the secret
rule itself uses, so the report can never print a value the analyzer
considers secret-shaped. `reporting.report.redact_application` applies the
same redaction to the `--format json` / `--output` JSON envelope — the
analysis itself always runs against the real, unredacted values (it has to,
to classify them); only output is ever redacted.

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

`analyze` exit codes: **1** means the input couldn't be parsed at all (bad
path, unrecognized format, malformed Compose — a `ParserError`); **2** means
analysis completed but found at least one CRITICAL finding; **0** means
analysis completed with only INFO/WARNING findings (or none). `--output PATH`
writes the full `AnalysisReport` as JSON regardless of `--format` — the same
schema `generate` is expected to accept as cached input in v0.3.
