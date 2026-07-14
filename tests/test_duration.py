from __future__ import annotations

import pytest

from gitops_scaffold.utils.duration import parse_duration_to_seconds


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("30s", 30),
        ("10s", 10),
        ("1m", 60),
        ("1m30s", 90),
        ("1h", 3600),
        ("1h30m", 5400),
        ("1500ms", 2),
        ("0s", 0),
    ],
)
def test_parse_duration_to_seconds(value: str, expected: int) -> None:
    assert parse_duration_to_seconds(value) == expected


def test_parse_duration_rejects_unrecognized_strings() -> None:
    with pytest.raises(ValueError, match="Not a valid duration string"):
        parse_duration_to_seconds("not-a-duration")
