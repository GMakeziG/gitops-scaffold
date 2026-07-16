# Changelog

## v0.3.0

### Added

- Real manifest generation: `ConfigMapGenerator`, `SecretExampleGenerator`,
  `DeploymentGenerator`, `ServiceGenerator`, `PersistentVolumeClaimGenerator`,
  `IngressGenerator` (optional, off by default), `KustomizationGenerator`,
  and `OutputReadmeGenerator`, orchestrated by `generators/pipeline.py::GenerationPipeline`.
- `generate` works end-to-end: accepts either a Compose file or a cached
  `AnalysisReport` JSON (`analyze --output`) — both converge on the same
  pipeline. `--app`/`--namespace` overrides, `--force`, and
  `--ingress-host/--ingress-class/--tls-secret/--cluster-issuer`.
- Overwrite-safety ledger (`generation_io.py`): uses a previous run's own
  `generation-report.json` to distinguish foreign files (always blocked),
  managed conflicts (blocked without `--force`), and orphaned files (blocked
  without `--force`, never deleted with it).
- `ManifestConsistencyValidator`: semantic cross-checks on top of
  `StructureValidator` — selectors, targetPorts, volume/PVC references,
  kustomization resource existence, resource name validity, redaction-marker
  leaks. Optional `validate --kubectl` (`utils/kubectl.py`), never a hard
  dependency.
- Shared, deterministic generation utilities: `utils/naming.py` (kebab-case
  + collision-safe truncation), `generators/labels.py` (pod
  labels/selectors), `generators/secret_classification.py` (derives
  secret/optional status from analysis findings, never re-running
  `looks_like_secret`), `generators/ports.py`, `generators/volumes.py`
  (PVC eligibility + shared-named-volume dedup), `generators/healthcheck.py`
  (Compose healthcheck → probe translation).
- `docs/generation.md` and `docs/configuration.md`.
- Golden-file trees (Audiobookshelf, multi-service) plus extensive targeted
  tests across every generator, the pipeline, overwrite safety, and the
  validator.

### Changed

- Deliberate v0.2→v0.3 behavior change: bind mounts (not just named
  volumes) are now converted to PVC scaffolding, excluding host-system
  paths and known/ambiguous file mounts — see `docs/generation.md`.
- `StructureValidator.EXPECTED_FILES` shrinks to the 3 always-required
  files; `secret.example.yaml` is conditional, not hard-required.
- `ManifestGenerator.generate()` now returns `GenerationOutcome`
  (`files` + `notes`) instead of a bare file tuple.

### Removed

- `generators/kustomize/checklist.py` (`ValidationChecklistGenerator`) and
  `templates/VALIDATION_CHECKLIST.md.j2` — the v0.3 output set has no
  separate checklist file; its job splits between README's "Needs review"
  section and `generation-report.json`'s notes.

## v0.2.0

### Added

- Real `ComposeParser`: services, image, command, entrypoint, environment
  (map + list), ports (short + long), volumes (short + long), user,
  healthcheck, depends_on, restart, `deploy.resources`, labels, network
  aliases — see `docs/compose-support.md`.
- All 8 planned detection rules, plus a 9th (`image.py`, image reference
  hygiene), and deterministic confidence scoring (`analyzer/scoring.py`).
- `DefaultAnalyzer`: the composite analyzer wiring every rule together plus
  cross-service checks (port collisions, "no services defined").
- `analyze` works end-to-end: `--format table|json`, `--output PATH` (a
  stable `AnalysisReport` JSON envelope), and a 0/1/2 exit-code convention.
- Parser plugin architecture: stub `Parser` subclasses for Dockerfile, Helm,
  Kubernetes, and GitHub-repository input, plus `parsers/registry.py`.
- `docs/compose-support.md`: supported/unsupported field table, the four
  environment value states, the confidence formula, known limitations.
- Golden-file and unit tests for the parser, all 9 rules, scoring, and the
  CLI (exit codes, JSON round-trip, secret redaction).

### Changed

- `Reporter.render` now takes `(app, result)` instead of just `(result)`, so
  it can print a full inventory alongside findings.
- `ServiceDefinition.image` and `VolumeMount.source` are now optional
  (`str | None`) to represent build-only services and anonymous volumes.

### Removed

- `EnvVar.is_secret` — secret classification now lives entirely in
  `Finding`s plus a shared `looks_like_secret` predicate, since the field
  was never actually settable on a frozen model.

## v0.1.0

### Added

- Project scaffolding
- CLI
- Parser interfaces
- Analyzer interfaces
- Generator interfaces
- Validator interfaces
- Jinja2 templates
- Architecture documentation
- Roadmap
- Unit tests
