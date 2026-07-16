from __future__ import annotations

from pathlib import Path

import yaml

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.kustomize.deployment import DeploymentGenerator
from gitops_scaffold.generators.kustomize.service import ServiceGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    PortMapping,
    Protocol,
    ServiceDefinition,
)


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _analysis() -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=1.0)


def test_no_service_when_no_ports() -> None:
    service = ServiceDefinition(name="worker", image="x:1.0")
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
    assert outcome.notes[0].category.value == "skipped"


def test_no_service_when_image_missing() -> None:
    service = ServiceDefinition(name="worker", image=None, ports=(PortMapping(container_port=80),))
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
    # DeploymentGenerator owns the "no image" skip note, not ServiceGenerator.
    assert outcome.notes == ()


def test_service_type_is_cluster_ip_by_default() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["type"] == "ClusterIP"


def test_service_port_uses_container_port_not_host_port() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    content = outcome.files[0].content
    doc = yaml.safe_load(content)
    port = doc["spec"]["ports"][0]
    assert port["port"] == 80
    assert "13378" not in content


def test_target_port_references_container_port_name() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    port = doc["spec"]["ports"][0]
    assert port["targetPort"] == port["name"]


def test_multiple_ports_and_protocols() -> None:
    service = ServiceDefinition(
        name="dns",
        image="x:1.0",
        ports=(
            PortMapping(container_port=53, protocol=Protocol.TCP),
            PortMapping(container_port=53, protocol=Protocol.UDP),
        ),
    )
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    protocols = {p["protocol"] for p in doc["spec"]["ports"]}
    assert protocols == {"TCP", "UDP"}
    assert len(doc["spec"]["ports"]) == 2


def test_selector_matches_deployment_pod_labels() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    app = _app(service)
    analysis = _analysis()
    service_doc = yaml.safe_load(ServiceGenerator().generate(app, analysis).files[0].content)
    deployment_doc = yaml.safe_load(DeploymentGenerator().generate(app, analysis).files[0].content)
    assert service_doc["spec"]["selector"] == deployment_doc["spec"]["selector"]["matchLabels"]


def test_target_port_matches_deployment_container_port_name() -> None:
    service = ServiceDefinition(
        name="web", image="x:1.0", ports=(PortMapping(container_port=8080),)
    )
    app = _app(service)
    analysis = _analysis()
    service_doc = yaml.safe_load(ServiceGenerator().generate(app, analysis).files[0].content)
    deployment_doc = yaml.safe_load(DeploymentGenerator().generate(app, analysis).files[0].content)
    container_port_names = {
        p["name"] for p in deployment_doc["spec"]["template"]["spec"]["containers"][0]["ports"]
    }
    assert service_doc["spec"]["ports"][0]["targetPort"] in container_port_names


def test_port_override_applied_only_for_single_port_service() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="x:1.0",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    settings = ScaffoldSettings(port_overrides={"audiobookshelf": 3005})
    outcome = ServiceGenerator(settings).generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["ports"][0]["port"] == 3005


def test_no_duplicate_port_override_notes_across_generators() -> None:
    # plan_ports() is called independently by both generators; only
    # DeploymentGenerator should surface the resulting note.
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        ports=(PortMapping(container_port=80), PortMapping(container_port=443)),
    )
    settings = ScaffoldSettings(port_overrides={"web": 3005})
    app = _app(service)
    analysis = _analysis()

    deployment_notes = DeploymentGenerator(settings).generate(app, analysis).notes
    service_notes = ServiceGenerator(settings).generate(app, analysis).notes

    assert any("port_overrides" in n.message for n in deployment_notes)
    assert not any("port_overrides" in n.message for n in service_notes)


def test_multi_service_uses_subdirectory_path() -> None:
    web = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    db = ServiceDefinition(
        name="db", image="postgres:16", ports=(PortMapping(container_port=5432),)
    )
    outcome = ServiceGenerator().generate(_app(web, db), _analysis())
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"web/service.yaml", "db/service.yaml"}


def test_audiobookshelf_service_uses_container_port_80_only() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="ghcr.io/advplyr/audiobookshelf:v2.35.1",
        ports=(PortMapping(container_port=80, host_port=13378),),
    )
    outcome = ServiceGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["ports"][0]["port"] == 80
    assert "13378" not in outcome.files[0].content
    assert "3005" not in outcome.files[0].content
    assert outcome.files[0].relative_path == Path("service.yaml")
