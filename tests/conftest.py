from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from gitops_scaffold.models.app import ApplicationDefinition, PortMapping, ServiceDefinition

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "compose"


@pytest.fixture
def compose_fixture() -> Callable[[str], Path]:
    """Returns a function mapping a fixture filename to its path.

    Usage: ``compose_fixture("audiobookshelf-compose.yml")`` or
    ``compose_fixture("malformed/null-services-compose.yml")``.
    """

    def _path(name: str) -> Path:
        return _FIXTURES_DIR / name

    return _path


@pytest.fixture
def sample_service() -> ServiceDefinition:
    return ServiceDefinition(
        name="web",
        image="nginx:1.27",
        ports=(PortMapping(container_port=80),),
    )


@pytest.fixture
def sample_app(sample_service: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(
        name="demo",
        services=(sample_service,),
        source_format="docker-compose",
        source_path="docker-compose.yml",
    )
