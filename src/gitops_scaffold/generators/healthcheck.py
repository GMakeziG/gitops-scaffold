"""Shared Compose healthcheck → Kubernetes probe translation.

Faithful, mechanical translation of what Compose already declared — not a
guessed ``httpGet``. Compose healthcheck semantics don't map exactly onto
Kubernetes readiness/liveness/startup probes (see ``docs/generation.md`` for
the specific gaps); this module documents each approximation at the point
it's made rather than pretending they're equivalent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from gitops_scaffold.models.app import HealthCheck


@dataclass(frozen=True)
class PlannedProbe:
    command: tuple[str, ...]
    period_seconds: int | None = None
    timeout_seconds: int | None = None
    failure_threshold: int | None = None


def exec_command(test: tuple[str, ...] | str | None) -> tuple[str, ...] | None:
    """Translates a Compose ``healthcheck.test`` into a Kubernetes ``exec.command``."""
    if test is None:
        return None
    if isinstance(test, str):
        return ("/bin/sh", "-c", test)
    if not test:
        return None
    if test[0] == "CMD-SHELL" and len(test) > 1:
        return ("/bin/sh", "-c", test[1])
    if test[0] == "CMD":
        return tuple(test[1:])
    return tuple(test)


def plan_readiness_or_liveness_probe(health_check: HealthCheck) -> PlannedProbe | None:
    """Builds a probe using exactly what Compose declared — no invented fallbacks.

    Fields Compose didn't declare (timeout, retries) are simply omitted from
    the rendered probe, letting Kubernetes apply its own defaults, rather
    than fabricating a value that happens to match them.
    """
    command = exec_command(health_check.test)
    if command is None:
        return None
    return PlannedProbe(
        command=command,
        period_seconds=health_check.interval_seconds,
        timeout_seconds=health_check.timeout_seconds,
        failure_threshold=health_check.retries,
    )


def plan_startup_probe(health_check: HealthCheck) -> tuple[PlannedProbe | None, bool]:
    """Builds a startupProbe when ``start_period_seconds`` is present.

    Unlike readiness/liveness, a startupProbe's ``failureThreshold`` is
    computed *from* ``periodSeconds`` (to approximate the total allowed
    startup window Compose's ``start_period`` describes), so ``periodSeconds``
    must always be rendered here, even when Compose didn't declare an
    interval — in that case a 10-second fallback cadence is used. Returns
    ``(probe, used_fallback_period)`` so the caller can note the fallback.
    """
    if health_check.start_period_seconds is None:
        return None, False
    command = exec_command(health_check.test)
    if command is None:
        return None, False

    used_fallback_period = health_check.interval_seconds is None
    period_seconds = health_check.interval_seconds or 10
    failure_threshold = max(1, math.ceil(health_check.start_period_seconds / period_seconds))
    return (
        PlannedProbe(
            command=command, period_seconds=period_seconds, failure_threshold=failure_threshold
        ),
        used_fallback_period,
    )
