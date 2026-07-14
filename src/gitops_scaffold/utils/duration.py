"""Parses Compose-style duration strings (``"30s"``, ``"1m30s"``, ``"1h"``).

Used for healthcheck timing fields (``interval``, ``timeout``, ``start_period``).
"""

from __future__ import annotations

import re

_DURATION_PATTERN = re.compile(r"(\d+)(h|ms|m|s)")


def parse_duration_to_seconds(value: str) -> int:
    """Parse a Compose duration string into whole seconds.

    Supports the ``h``/``m``/``s``/``ms`` units Compose allows, in any
    combination (e.g. ``"1h30m"``, ``"90s"``). Raises :class:`ValueError` if
    ``value`` doesn't match the expected duration grammar at all.
    """
    matches = _DURATION_PATTERN.findall(value)
    if not matches:
        raise ValueError(f"Not a valid duration string: {value!r}")

    unit_seconds = {"h": 3600, "m": 60, "s": 1, "ms": 1 / 1000}
    total = sum(int(amount) * unit_seconds[unit] for amount, unit in matches)
    return round(total)
