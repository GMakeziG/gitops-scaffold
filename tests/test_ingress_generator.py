from __future__ import annotations

import yaml

from gitops_scaffold.generators.ingress_config import IngressConfig
from gitops_scaffold.generators.kustomize.ingress import IngressGenerator
from gitops_scaffold.generators.kustomize.kustomization import KustomizationGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, PortMapping, ServiceDefinition


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _analysis() -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=1.0)


def _config() -> IngressConfig:
    return IngressConfig(
        host="audiobooks.example.com",
        ingress_class="traefik",
        tls_secret="audiobooks-tls",
        cluster_issuer="letsencrypt-production",
    )


def test_disabled_by_default() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = IngressGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
    assert outcome.notes == ()


def test_generates_when_config_supplied() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = IngressGenerator(ingress_config=_config()).generate(_app(service), _analysis())
    assert len(outcome.files) == 1
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["kind"] == "Ingress"
    assert doc["spec"]["ingressClassName"] == "traefik"
    assert doc["spec"]["rules"][0]["host"] == "audiobooks.example.com"
    assert doc["spec"]["tls"][0]["secretName"] == "audiobooks-tls"
    assert (
        doc["metadata"]["annotations"]["cert-manager.io/cluster-issuer"] == "letsencrypt-production"
    )


def test_skipped_when_no_service_has_ports() -> None:
    service = ServiceDefinition(name="worker", image="x:1.0")
    outcome = IngressGenerator(ingress_config=_config()).generate(_app(service), _analysis())
    assert outcome.files == ()
    assert outcome.notes[0].category.value == "skipped"


def test_only_first_candidate_gets_ingress() -> None:
    web = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    admin = ServiceDefinition(name="admin", image="x:1.0", ports=(PortMapping(container_port=81),))
    outcome = IngressGenerator(ingress_config=_config()).generate(_app(web, admin), _analysis())
    assert len(outcome.files) == 1
    assert "web" in str(outcome.files[0].relative_path)
    assert any("admin" in n.message for n in outcome.notes)


def test_kustomization_includes_ingress_for_selected_service() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = KustomizationGenerator(ingress_config=_config()).generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert "ingress.yaml" in doc["resources"]


def test_kustomization_excludes_ingress_when_not_configured() -> None:
    service = ServiceDefinition(name="web", image="x:1.0", ports=(PortMapping(container_port=80),))
    outcome = KustomizationGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert "ingress.yaml" not in doc["resources"]
