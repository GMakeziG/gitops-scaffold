from __future__ import annotations

import pytest

from gitops_scaffold.models.app import ApplicationDefinition, PortMapping, ServiceDefinition


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
