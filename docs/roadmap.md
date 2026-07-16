# Roadmap

This roadmap tracks milestones toward a 1.0 release. It will be revised as
real-world usage surfaces gaps the design didn't anticipate.

## v0.1 — Project scaffolding (this milestone)

- [x] Package layout: `parsers/`, `analyzer/`, `generators/`, `models/`,
      `validators/`, `reporting/`, `config/`, `utils/`.
- [x] `pyproject.toml` with Ruff, ty, and pytest configured.
- [x] Pydantic v2 intermediate representation (`models/app.py`,
      `models/analysis.py`, `models/generation.py`).
- [x] Parser / Analyzer / Generator / Validator interfaces (abstract base
      classes), with stub implementations that fail loudly rather than
      silently.
- [x] Jinja2 template placeholders for every planned manifest kind.
- [x] `StructureValidator`: a fully working structural check for generated
      output directories.
- [x] Typer CLI skeleton: `analyze`, `generate`, `validate`.
- [x] Unit tests for every interface and the working `validate` path.
- **No Docker Compose parsing yet** — `analyze` and `generate` exit
  non-zero with a clear "not yet implemented" message.

## v0.2 — Docker Compose parsing + basic analysis (done)

- [x] `ComposeParser`: services, image, command, entrypoint, environment
      (map + list), ports (short + long), volumes (short + long), user,
      healthcheck, depends_on, restart, `deploy.resources`, labels, network
      aliases — see `docs/compose-support.md` for the exact field table.
- [x] All 8 originally-planned detection rules, plus a 9th (`image.py`, image
      reference hygiene — see `docs/compose-support.md`).
- [x] Deterministic, explainable confidence scoring (`analyzer/scoring.py`).
- [x] `analyze` produces a real confidence report end-to-end, with
      `--format table|json`, `--output PATH` (the JSON envelope `generate`
      will accept in v0.3), and a 0/1/2 exit-code convention.
- [x] Parser plugin architecture: `Parser` subclass stubs for Dockerfile,
      Helm, Kubernetes, and GitHub-repository input, plus a
      `parsers/registry.py` dispatcher — adding a real one later never
      touches the CLI.
- [x] Golden-file + unit tests for the parser, all 9 rules, confidence
      scoring, and the CLI (including exit codes and secret redaction).
- Deferred to later milestones: `build:`-context support, port
  ranges, OCI image introspection for UID/tag inference (v0.6), YAML
  line-number provenance.

## v0.3 — Manifest generation (done)

- [x] All 7 core generators (ConfigMap, Secret example, Deployment, Service,
      PVC, Ingress, Kustomization) plus `OutputReadmeGenerator` (a deliberate
      exception to the `ManifestGenerator` interface — see
      `docs/architecture.md`), orchestrated by `generators/pipeline.py::GenerationPipeline`.
      The v0.1-scaffolded `ValidationChecklistGenerator` was removed — its job
      splits between README's "Needs review" section and
      `generation-report.json`'s notes.
- [x] `generate` accepts either a Compose file or a previously saved
      `AnalysisReport` JSON (produced by `analyze --output`) as input —
      both converge on the same pipeline; see `docs/generation.md`.
- [x] Deliberate v0.2→v0.3 behavior change: bind mounts (not just named
      volumes) become PVC scaffolding, excluding host-system paths and
      known/ambiguous file mounts — see `docs/generation.md`.
- [x] Entrypoint/command mapping, healthcheck→probe translation
      (readiness by default, opt-in liveness, startupProbe from
      start_period), and required-vs-optional `secretKeyRef` handling —
      all verified against the actual Compose/Kubernetes semantics, not
      just the common case.
- [x] Overwrite-safety ledger (`generation_io.py`): foreign files always
      block, managed conflicts and orphaned files block without `--force`.
- [x] `ManifestConsistencyValidator`: semantic cross-checks (selectors,
      targetPorts, volume/PVC references, kustomization resource
      existence, resource name validity, redaction-marker leaks) on top
      of `StructureValidator`'s file-presence check. Optional
      `validate --kubectl` integration, never a hard dependency.
- [x] Golden-file tests (Audiobookshelf, multi-service) plus extensive
      targeted assertions (secrets, multi-port, persistent volumes,
      overwrite/--force, direct-Compose-vs-cached-report parity) across
      every generator's own test module.
- Deferred: Helm generation, OpenBao/ExternalSecret generation, Cloudflare
  Tunnel, live `kubectl apply`, Flux reconciliation, `build:`-context
  support, port ranges, emptyDir wiring for tmpfs.

## v0.4 — Deeper analysis

- Health check detection: infer HTTP readiness endpoints where possible;
  flag services with none.
- Runtime user detection: infer UID/GID from image metadata where possible.
- Security risk detection: privileged mode, host network/PID, dangerous
  capability grants, root filesystem writes.
- Persistence detection: distinguish ephemeral scratch volumes from data
  that needs a PVC.

## v0.5 — Validation depth

- Schema-validate generated manifests against the Kubernetes OpenAPI spec.
- Optional `kustomize build` / `kubeconform` integration in `validate`.
- `--strict` mode: fail `generate` if unresolved `REVIEW REQUIRED` markers
  remain past a configurable threshold.

## v0.6 — Additional input formats

- Dockerfile-only projects (no Compose file): infer a minimal
  `ApplicationDefinition` from `EXPOSE`, `USER`, `HEALTHCHECK`, `VOLUME`.
- OCI image introspection: pull image config/manifest to fill gaps Compose
  doesn't express (exposed ports, default user).

## v0.7 — GitHub repository input

- Given a GitHub repo URL, locate and parse its Compose file / Dockerfile
  automatically as a convenience entrypoint.

## v0.8 — Multi-environment output

- Kustomize overlays (`base/` + `overlays/dev,staging,prod`) instead of a
  single flat output directory.
- Per-environment `ScaffoldSettings` overrides.

## v0.9 — Polish and documentation

- Full user guide in `docs/`, covering every detection rule and generator
  decision with examples.
- Expanded example gallery under `examples/`.
- Performance pass on large, multi-service Compose files.

## v1.0 — Stable release

- API and CLI stability guarantees.
- Semantic versioning commitment for the `ApplicationDefinition` IR and the
  `Parser` / `Analyzer` / `ManifestGenerator` / `Validator` interfaces, so
  third parties can build additional parsers/generators against them.

## Explicitly out of scope for 1.0

- Helm chart generation. The project targets plain Kubernetes manifests for
  FluxCD + Kustomize; Helm output may be reconsidered post-1.0 as a separate
  generator backend, not a default.
- Automatic secret value generation or storage. `gitops-scaffold` documents
  what secrets an application needs; it never creates, stores, or transmits
  real secret values.
