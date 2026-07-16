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
                │  Validators  │──▶ structural + semantic consistency checks
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
returns a `GenerationOutcome` (`files` + `notes`), usually by rendering a
Jinja2 template from `gitops_scaffold/templates/` via the shared
`generators/rendering.py::render_template`. Each generator owns exactly one
resource kind (ConfigMap, Secret example, Deployment, Service, PVC, Ingress,
Kustomization) — see `gitops_scaffold/generators/kustomize/`.
`GenerationNote` (`category`: `assumption`/`skipped`/`warning`,
`requires_review`) is how a generator explains a decision that isn't a file
by itself — see `docs/generation.md` for the full Compose→Kubernetes mapping
each one implements.

Two hard rules apply to every generator:

1. **Never generate a real Kubernetes `Secret`.** `secret.example.yaml` is
   always a placeholder with `CHANGE_ME` values, and never reads
   `EnvVar.value` at all for a secret-classified variable — only its name;
   real secrets are the operator's responsibility, managed through whatever
   secret manager (SealedSecrets, External Secrets Operator, SOPS) fits
   their cluster.
2. **Never fill in a value the analysis wasn't confident about.** Where
   information is missing, the rendered manifest gets a `TODO` or
   `REVIEW REQUIRED` comment (and a matching `GenerationNote`) instead of a
   plausible-looking default.

Several generators independently recompute "would a ConfigMap/Service/PVC
exist for this service" via the exact same shared, deterministic helpers the
owning generator itself uses (`kustomize/configmap.py::has_configmap_data`,
`generators/ports.py::plan_ports`, `generators/volumes.py::plan_volumes`) —
since these are pure functions of `(app, analysis, settings)`, the same
inputs every generator receives, there's no way for two generators to
disagree about whether a given file exists. `OutputReadmeGenerator` is the
one exception: it needs the *aggregated* notes from every other generator
(free-form prose, not independently re-derivable), so it deliberately does
not implement the `ManifestGenerator` interface — see its docstring.

`generators/pipeline.py::GenerationPipeline` is the single place generation
actually happens: it runs every generator over an application and assembles
one `GenerationOutcome`, run identically whether the input was a fresh
Compose parse or a cached `AnalysisReport` (see `cli.py`'s input resolution).

Helm chart generation is explicitly out of scope — output is plain
Kubernetes manifests laid out for FluxCD + Kustomize.

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
expected shape (always-required files present, no unresolved review
markers) — purely filesystem-level, no YAML parsing.
`ManifestConsistencyValidator` (v0.3) goes deeper: parses every YAML file
(including multi-document `pvc.yaml`) and cross-references
Service↔Deployment↔PVC the way a human reviewer would — selectors actually
matching pod labels, `targetPort` actually matching a named container port,
`volumeMounts` actually matching declared volumes, `persistentVolumeClaim.claimName`
actually pointing at a PVC that exists, `kustomization.yaml` resources
actually existing (files *or* directories) and never including the three
forbidden files, resource names being valid, and the redaction marker never
appearing anywhere (see `docs/generation.md`'s Validation section for the
full list). `validate --kubectl` optionally shells out to
`kubectl kustomize` (`utils/kubectl.py`) if `kubectl` is on `PATH` — never a
hard dependency.

## Configuration (`gitops_scaffold.config`)

`ScaffoldSettings` holds opinionated, overridable defaults (namespace,
Service type, resource request/limit defaults, PVC size/access mode, extra
labels, liveness-probe opt-in, port overrides, secret name patterns) that
apply across all generated manifests for a project, loaded from an optional
`.gitops-scaffold.yaml` — see `docs/configuration.md` for the full field
table. Ingress configuration is deliberately CLI-flag-only, not part of this
persisted settings object (see `generators/ingress_config.py`).

## CLI (`gitops_scaffold.cli`)

A thin Typer layer wiring the stages above to three commands: `analyze`,
`generate`, and `validate`. The CLI itself contains no business logic — it
only orchestrates parser → analyzer → reporter/generator → validator calls
and renders their results. `generate`'s heavier logic (input resolution,
overwrite-safety ledger, staged file writes) lives in `generation_io.py`,
kept out of `cli.py` for the same reason.

Exit codes for both `analyze` and `generate`: **1** means the input couldn't
be parsed/resolved at all (bad path, unrecognized format, malformed Compose,
malformed report, a bad `--ingress-*` combination, or an overwrite-safety
block); **2** means the run completed but the underlying analysis has at
least one CRITICAL finding; **0** means it completed with only
INFO/WARNING findings (or none). `analyze --output PATH` writes the full
`AnalysisReport` as JSON regardless of `--format` — the exact schema
`generate` accepts as cached input (see `docs/generation.md`).
