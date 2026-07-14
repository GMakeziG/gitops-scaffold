# Changelog

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
