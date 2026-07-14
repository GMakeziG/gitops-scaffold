from __future__ import annotations

from pathlib import Path

import pytest

from gitops_scaffold.parsers.compose import ComposeParser


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("docker-compose.yml", True),
        ("docker-compose.yaml", True),
        ("compose.yaml", True),
        ("Dockerfile", False),
        ("values.yaml", False),
    ],
)
def test_can_parse_matches_compose_filenames(filename: str, expected: bool) -> None:
    assert ComposeParser().can_parse(Path(filename)) is expected


def test_parse_is_not_yet_implemented(tmp_path: Path) -> None:
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("services: {}\n")

    with pytest.raises(NotImplementedError):
        ComposeParser().parse(compose_file)
