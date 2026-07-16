from __future__ import annotations

from pathlib import Path

import yaml

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.kustomize.pvc import PersistentVolumeClaimGenerator
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition, VolumeMount


def _app(*services: ServiceDefinition) -> ApplicationDefinition:
    return ApplicationDefinition(name="demo", services=services, source_format="docker-compose")


def _analysis() -> AnalysisResult:
    return AnalysisResult(application_name="demo", confidence=1.0)


def test_no_pvc_when_no_eligible_volumes() -> None:
    service = ServiceDefinition(name="web", image="x:1.0")
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()


def test_named_volume_pvc_single_service() -> None:
    service = ServiceDefinition(
        name="db",
        image="postgres:16",
        volumes=(
            VolumeMount(
                source="db-data",
                target="/var/lib/postgresql/data",
                mount_type="volume",
                is_named_volume=True,
            ),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert len(outcome.files) == 1
    file = outcome.files[0]
    assert file.relative_path == Path("pvc.yaml")
    assert file.requires_review is True

    doc = yaml.safe_load(file.content)
    assert doc["kind"] == "PersistentVolumeClaim"
    assert doc["metadata"]["name"] == "db-data"
    assert doc["spec"]["accessModes"] == ["ReadWriteOnce"]
    assert doc["spec"]["resources"]["requests"]["storage"] == "1Gi"
    assert "REVIEW REQUIRED" in file.content


def test_audiobookshelf_bind_mounts_produce_four_pvcs() -> None:
    service = ServiceDefinition(
        name="audiobookshelf",
        image="ghcr.io/advplyr/audiobookshelf:v2.35.1",
        volumes=(
            VolumeMount(source="./audiobooks", target="/audiobooks", mount_type="bind"),
            VolumeMount(source="./podcasts", target="/podcasts", mount_type="bind"),
            VolumeMount(source="./config", target="/config", mount_type="bind"),
            VolumeMount(source="./metadata", target="/metadata", mount_type="bind"),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert len(outcome.files) == 1
    docs = list(yaml.safe_load_all(outcome.files[0].content))
    assert len(docs) == 4
    targets = set()
    for doc in docs:
        assert doc["kind"] == "PersistentVolumeClaim"
        targets.add(doc["spec"]["resources"]["requests"]["storage"])
    assert targets == {"1Gi"}


def test_docker_socket_and_tmpfs_are_skipped_no_pvc() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="/var/run/docker.sock", target="/var/run/docker.sock", mount_type="bind"
            ),
            VolumeMount(source=None, target="/tmp/cache", mount_type="tmpfs"),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
    assert any("host-system path" in n.message for n in outcome.notes)
    assert any("ephemeral" in n.message for n in outcome.notes)


def test_ambiguous_file_mount_skipped_with_review_note() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="./nginx.conf",
                target="/etc/nginx/nginx.conf",
                read_only=True,
                mount_type="bind",
            ),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
    note = next(n for n in outcome.notes if "nginx.conf" in n.message)
    assert note.requires_review is True


def test_anonymous_volume_produces_pvc() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(VolumeMount(source=None, target="/data", mount_type="volume"),),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["kind"] == "PersistentVolumeClaim"


def test_shared_named_volume_generates_root_pvc() -> None:
    web = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="db-data", target="/data", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    backup = ServiceDefinition(
        name="backup",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="db-data", target="/backup-src", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(web, backup), _analysis())
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"pvc.yaml"}
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["metadata"]["name"] == "db-data"
    # A PVC shared by more than one service has no service-scoped identity label.
    assert "app.kubernetes.io/name" not in doc["metadata"]["labels"]


def test_single_service_named_volume_among_multiple_still_lands_in_service_dir() -> None:
    web = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="web-cache", target="/cache", mount_type="volume", is_named_volume=True
            ),
        ),
    )
    db = ServiceDefinition(name="db", image="postgres:16")
    outcome = PersistentVolumeClaimGenerator().generate(_app(web, db), _analysis())
    paths = {str(f.relative_path) for f in outcome.files}
    assert paths == {"web/pvc.yaml"}
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["metadata"]["labels"]["app.kubernetes.io/name"] == "web"


def test_read_only_volume_reflected_in_access_mode_defaults() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(
                source="cache",
                target="/cache",
                mount_type="volume",
                is_named_volume=True,
                read_only=True,
            ),
        ),
    )
    settings = ScaffoldSettings(default_access_mode="ReadOnlyMany")
    outcome = PersistentVolumeClaimGenerator(settings).generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["accessModes"] == ["ReadOnlyMany"]


def test_configured_pvc_size_is_used() -> None:
    service = ServiceDefinition(
        name="web",
        image="x:1.0",
        volumes=(
            VolumeMount(source="data", target="/data", mount_type="volume", is_named_volume=True),
        ),
    )
    settings = ScaffoldSettings(default_pvc_size="5Gi")
    outcome = PersistentVolumeClaimGenerator(settings).generate(_app(service), _analysis())
    doc = yaml.safe_load(outcome.files[0].content)
    assert doc["spec"]["resources"]["requests"]["storage"] == "5Gi"


def test_no_pvc_when_image_missing() -> None:
    service = ServiceDefinition(
        name="web",
        image=None,
        volumes=(
            VolumeMount(source="data", target="/data", mount_type="volume", is_named_volume=True),
        ),
    )
    outcome = PersistentVolumeClaimGenerator().generate(_app(service), _analysis())
    assert outcome.files == ()
