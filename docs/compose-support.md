# Docker Compose support (v0.2)

This documents exactly what `ComposeParser` understands, what it doesn't,
and how it represents ambiguity — the contract behind "never silently
ignore unsupported fields."

## Supported fields

| Compose field | Normalized to | Notes |
| --- | --- | --- |
| `services.<name>.image` | `ServiceDefinition.image` | `None` if absent (e.g. `build:`-only services) |
| `command` (string or list) | `ServiceDefinition.command` | String form parsed with `shlex.split()` |
| `entrypoint` (string or list) | `ServiceDefinition.entrypoint` | Same as `command` |
| `environment` (map or list) | `ServiceDefinition.environment` | See "The four environment value states" below |
| `env_file` (string or list) | `ServiceDefinition.env_files` | Paths only — file contents are never read |
| `ports` (short or long syntax) | `ServiceDefinition.ports` | See "Ports" below |
| `volumes` (short or long syntax) | `ServiceDefinition.volumes` | See "Volumes" below |
| `user` | `ServiceDefinition.runtime_user` | uid/gid resolve independently; `raw` always preserved |
| `healthcheck` | `ServiceDefinition.health_check` | `test`, `interval`, `timeout`, `start_period`, `retries`, `disable` |
| `depends_on` (list or map) | `ServiceDefinition.depends_on` | Names only; long-form `condition` becomes an unsupported-field note |
| `restart` | `ServiceDefinition.restart_policy` | Verbatim string |
| `deploy.resources.reservations`/`limits` | `ServiceDefinition.resources` | Raw Compose strings, not converted to Kubernetes units |
| `labels` (map or list) | `ServiceDefinition.labels` | |
| `networks` (map form `aliases`) | `ServiceDefinition.network_aliases` | Flattened across all networks the service joins |
| `network_mode` | `ServiceDefinition.network_mode` | Matched literally against `"host"` for the security rule |
| `privileged` | `ServiceDefinition.privileged` | |
| top-level `name` | `ApplicationDefinition.name` | Falls back to the file's stem |
| top-level `volumes`/`networks` | used only to resolve names/aliases | Driver/external/IPAM options aren't parsed |

## Unsupported fields

Anything read but not modeled above becomes a dotted-path string in
`ServiceDefinition.unsupported_fields` or `ApplicationDefinition.unsupported_fields`
— never silently dropped. `DefaultAnalyzer` turns every one of these into a
`compose-unsupported-field` WARNING finding. Examples: `services.web.container_name`,
`services.web.build`, `services.web.expose`, `services.web.cap_add`,
`services.web.deploy.replicas`, `depends_on.db.condition`, top-level `secrets`,
top-level `configs`.

Two categories are deliberately **not** reported as unsupported, since ignoring
them is itself the correct, spec-compliant behavior:

- `x-*` extension keys (top-level or per-service) — Compose-spec convention
  for vendor/tool-specific data.
- The deprecated top-level `version:` key.

## The four environment value states

Compose lets a variable's value be "unknown" in more than one way, and they
mean different things for secret analysis (`analyzer/rules/secrets.py`):

| Compose syntax | `EnvVar.value` | Meaning |
| --- | --- | --- |
| `KEY: literal` / `"KEY=literal"` | `"literal"` | Written directly in this file |
| `KEY: ${OTHER}` / `"KEY=${OTHER}"` | `"${OTHER}"` | Interpolated from another variable — classified separately, not treated as literal |
| `KEY: ""` / `"KEY="` | `""` | Explicitly declared empty |
| `KEY:` (null) / bare `"KEY"` in a list | `None` | Not written here at all — resolved from the shell environment running Compose |

## Ports

Short syntax (`HOST_IP:HOST_PORT:CONTAINER_PORT/PROTOCOL`, with `HOST_IP` and
`HOST_PORT` optional) and long syntax (`target`/`published`/`protocol`/`mode`)
are both supported, including bracketed IPv6 host addresses. A non-default
host IP is recorded as an unsupported-field note rather than a new field
(inert for analysis purposes today). **Port ranges** (`8080-8090:80-90`, or a
string range in long-syntax `published:`) are not modeled as a `PortMapping`
at all — they're recorded as unsupported and skipped.

## Volumes

Short syntax (`SOURCE:TARGET:ro`, or a bare path for an anonymous volume) and
long syntax (`type`/`source`/`target`/`read_only`) are both supported.
`mount_type` is one of `"bind"`, `"volume"`, or `"tmpfs"`. A bare-name source
(no leading `/`, `./`, `../`, or `~`) is always treated as a named volume,
matching Compose's own disambiguation rule — whether or not it's declared
under the top-level `volumes:` section (an undeclared reference gets an
unsupported-field note, but is still classified as a named volume).

## Confidence scoring

See `analyzer/scoring.py`. Each service starts at 100%; a CRITICAL finding
attributed to it costs 15 points, a WARNING costs 5, INFO costs nothing —
floored at 0. The application-level score is the average across all services
(or 100% if there are none), then the same per-finding costs are subtracted
again for app-level findings (cross-service port collisions, "no services
defined") before a final floor/ceiling clamp to `[0%, 100%]`. Pure function
of the findings — fully deterministic and unit-tested in isolation
(`tests/test_scoring.py`).

## Known limitations

- No YAML line-number tracking. `Finding.field_path` points to a dotted
  logical path (e.g. `environment.API_TOKEN`), not a line number.
- No `build:` context support — a build-only service (no `image:`) is
  flagged CRITICAL ("no image"), not built.
- Port ranges and long-syntax range `published:` values aren't modeled.
- Top-level `volumes:`/`networks:` driver/external/IPAM configuration isn't
  parsed — only names and aliases are consulted.
- `depends_on` long-form `condition`/`restart` sub-keys aren't kept on the
  IR (only the dependency name), though they are surfaced as unsupported
  fields so nothing is silently lost.
- Shell-vs-exec distinction for `command`/`entrypoint` isn't preserved after
  normalization — both are parsed into the same `tuple[str, ...]` shape.
