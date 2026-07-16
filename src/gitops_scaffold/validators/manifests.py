"""Semantic consistency checks for a generated GitOps output directory.

Unlike :class:`~gitops_scaffold.validators.structure.StructureValidator`
(which only checks that expected files exist), this parses every YAML file
and cross-references Service↔Deployment↔PVC the way a human reviewer would:
selectors actually matching pod labels, `targetPort` actually matching a
named container port, `volumeMounts` actually matching declared volumes,
`persistentVolumeClaim.claimName` actually pointing at a PVC that exists, and
`kustomization.yaml` resource lists actually pointing at files/directories
that exist (and never at the three files that must always be excluded).

There's no access here to the real secret values that were originally
detected (the validator only ever sees files already on disk), so "no
detected secret values appear in generated files" is checked the only way
that's actually possible without them: the redaction marker
(``"***REDACTED***"``) must never appear in any manifest — its presence
would mean a secret-shaped value was mishandled during generation rather
than properly excluded, which is itself a real bug worth catching.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.validators.base import Validator

#: Never allowed in a kustomization.yaml resources: list — see
#: generators/kustomize/kustomization.py.
FORBIDDEN_KUSTOMIZATION_RESOURCES = frozenset(
    {"secret.example.yaml", "README.md", "generation-report.json"}
)

#: The one value every secret.example.yaml entry must have — see
#: generators/kustomize/secret.py.
SECRET_PLACEHOLDER_VALUE = "CHANGE_ME"

#: A leaked redaction marker means a secret-shaped value slipped into a
#: manifest instead of being properly excluded — see reporting/report.py.
REDACTION_MARKER = "***REDACTED***"

_K8S_NAME_PATTERN = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_MAX_K8S_NAME_LENGTH = 253


class ManifestConsistencyValidator(Validator):
    """Parses and cross-references every manifest in a generated output directory."""

    def validate(self, output_dir: Path) -> tuple[Finding, ...]:
        findings: list[Finding] = []

        yaml_paths = sorted({*output_dir.rglob("*.yaml"), *output_dir.rglob("*.yml")})
        docs_by_path: dict[Path, list[Any]] = {}

        for path in yaml_paths:
            if not path.is_file():
                continue
            docs, parse_findings = _parse_yaml_documents(path, output_dir)
            findings.extend(parse_findings)
            if docs is not None:
                docs_by_path[path] = docs
                findings.extend(_check_resource_names(path, output_dir, docs))

        findings.extend(_check_redaction_marker(yaml_paths, output_dir))
        findings.extend(_check_kustomization_resources(docs_by_path, output_dir))
        findings.extend(_check_deployment_service_pvc_consistency(docs_by_path, output_dir))
        findings.extend(_check_secret_example_placeholders(docs_by_path, output_dir))

        return tuple(findings)


def _parse_yaml_documents(
    path: Path, output_dir: Path
) -> tuple[list[Any] | None, tuple[Finding, ...]]:
    try:
        raw_docs = list(yaml.safe_load_all(path.read_text()))
    except yaml.YAMLError as exc:
        return None, (
            Finding(
                code="manifest-invalid-yaml",
                message=f"{path.relative_to(output_dir)}: invalid YAML ({exc}).",
                severity=Severity.CRITICAL,
            ),
        )
    docs = [doc for doc in raw_docs if doc is not None]
    findings = tuple(
        Finding(
            code="manifest-invalid-structure",
            message=f"{path.relative_to(output_dir)}: a document is not a mapping.",
            severity=Severity.CRITICAL,
        )
        for doc in docs
        if not isinstance(doc, dict)
    )
    return docs, findings


#: Kustomize's `Kustomization` is a build-time config document, not a real,
#: named API object -- it legitimately has no `metadata.name` at all, unlike
#: every other kind this validator checks.
_KINDS_WITHOUT_REQUIRED_NAME = frozenset({"Kustomization"})


def _check_resource_names(path: Path, output_dir: Path, docs: list[Any]) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for doc in docs:
        if not isinstance(doc, dict) or ("apiVersion" not in doc and "kind" not in doc):
            continue
        kind = doc.get("kind", "resource")
        if kind in _KINDS_WITHOUT_REQUIRED_NAME:
            continue
        metadata = doc.get("metadata")
        name = metadata.get("name") if isinstance(metadata, dict) else None
        if not name:
            findings.append(
                Finding(
                    code="manifest-missing-name",
                    message=f"{path.relative_to(output_dir)}: {kind} is missing metadata.name.",
                    severity=Severity.CRITICAL,
                )
            )
        elif not _is_valid_k8s_name(name):
            findings.append(
                Finding(
                    code="manifest-invalid-name",
                    message=(
                        f"{path.relative_to(output_dir)}: '{name}' is not a valid Kubernetes "
                        f"resource name."
                    ),
                    severity=Severity.CRITICAL,
                )
            )
    return tuple(findings)


def _is_valid_k8s_name(name: str) -> bool:
    return bool(_K8S_NAME_PATTERN.match(name)) and len(name) <= _MAX_K8S_NAME_LENGTH


def _check_redaction_marker(yaml_paths: list[Path], output_dir: Path) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path in yaml_paths:
        if not path.is_file():
            continue
        if REDACTION_MARKER in path.read_text(errors="ignore"):
            findings.append(
                Finding(
                    code="manifest-redaction-leak",
                    message=(
                        f"{path.relative_to(output_dir)}: contains the redaction marker "
                        f"'{REDACTION_MARKER}' — a secret-shaped value may have been mishandled "
                        "during generation instead of properly excluded."
                    ),
                    severity=Severity.CRITICAL,
                )
            )
    return tuple(findings)


def _check_kustomization_resources(
    docs_by_path: dict[Path, list[Any]], output_dir: Path
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path, docs in docs_by_path.items():
        if path.name != "kustomization.yaml":
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            for resource in doc.get("resources") or []:
                if resource in FORBIDDEN_KUSTOMIZATION_RESOURCES:
                    findings.append(
                        Finding(
                            code="manifest-forbidden-kustomization-resource",
                            message=(
                                f"{path.relative_to(output_dir)}: lists forbidden resource "
                                f"'{resource}'."
                            ),
                            severity=Severity.CRITICAL,
                        )
                    )
                    continue
                # A resource may be a file *or* a directory (multi-service
                # root kustomizations reference service subdirectories) --
                # `.exists()`, not `.is_file()`.
                if not (path.parent / resource).exists():
                    findings.append(
                        Finding(
                            code="manifest-missing-kustomization-resource",
                            message=(
                                f"{path.relative_to(output_dir)}: resource '{resource}' does not "
                                "exist."
                            ),
                            severity=Severity.CRITICAL,
                        )
                    )
    return tuple(findings)


def _check_deployment_service_pvc_consistency(
    docs_by_path: dict[Path, list[Any]], output_dir: Path
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    by_dir: dict[Path, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for path, docs in docs_by_path.items():
        for doc in docs:
            if isinstance(doc, dict) and doc.get("kind"):
                by_dir[path.parent][doc["kind"]].append(doc)

    for directory, kinds in by_dir.items():
        deployments = kinds.get("Deployment", [])
        services = kinds.get("Service", [])
        pvc_names = {
            pvc["metadata"]["name"]
            for pvc in kinds.get("PersistentVolumeClaim", [])
            if isinstance(pvc.get("metadata"), dict) and "name" in pvc["metadata"]
        }

        for deployment in deployments:
            findings.extend(_check_deployment_volumes(deployment, pvc_names, directory, output_dir))

        for service in services:
            findings.extend(
                _check_service_against_deployments(service, deployments, directory, output_dir)
            )

    return tuple(findings)


def _pod_spec(deployment: dict[str, Any]) -> dict[str, Any]:
    return deployment.get("spec", {}).get("template", {}).get("spec", {}) or {}


def _pod_labels(deployment: dict[str, Any]) -> dict[str, Any]:
    return (
        deployment.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) or {}
    )


def _container_port_names(deployment: dict[str, Any]) -> set[str]:
    names = set()
    for container in _pod_spec(deployment).get("containers") or []:
        for port in container.get("ports") or []:
            if "name" in port:
                names.add(port["name"])
    return names


def _check_deployment_volumes(
    deployment: dict[str, Any], pvc_names: set[str], directory: Path, output_dir: Path
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    location = directory.relative_to(output_dir) if directory != output_dir else Path(".")
    pod_spec = _pod_spec(deployment)
    volume_names = {v.get("name") for v in pod_spec.get("volumes") or []}

    for container in pod_spec.get("containers") or []:
        for mount in container.get("volumeMounts") or []:
            if mount.get("name") not in volume_names:
                findings.append(
                    Finding(
                        code="manifest-volume-mount-mismatch",
                        message=(
                            f"{location}: volumeMount '{mount.get('name')}' has no matching "
                            "volume in the pod spec."
                        ),
                        severity=Severity.CRITICAL,
                    )
                )

    for volume in pod_spec.get("volumes") or []:
        claim = (volume.get("persistentVolumeClaim") or {}).get("claimName")
        if claim and claim not in pvc_names:
            findings.append(
                Finding(
                    code="manifest-pvc-reference-missing",
                    message=(
                        f"{location}: volume '{volume.get('name')}' references PVC '{claim}', "
                        "which doesn't exist."
                    ),
                    severity=Severity.CRITICAL,
                )
            )

    return tuple(findings)


def _check_service_against_deployments(
    service: dict[str, Any],
    deployments: list[dict[str, Any]],
    directory: Path,
    output_dir: Path,
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    location = directory.relative_to(output_dir) if directory != output_dir else Path(".")

    selector = service.get("spec", {}).get("selector") or {}
    if deployments and selector:
        matches_any = any(selector.items() <= _pod_labels(d).items() for d in deployments)
        if not matches_any:
            findings.append(
                Finding(
                    code="manifest-selector-mismatch",
                    message=f"{location}: Service selector doesn't match any Deployment's pod labels.",
                    severity=Severity.CRITICAL,
                )
            )

    all_port_names = {name for d in deployments for name in _container_port_names(d)}
    for port in service.get("spec", {}).get("ports") or []:
        target = port.get("targetPort")
        if isinstance(target, str) and target not in all_port_names:
            findings.append(
                Finding(
                    code="manifest-targetport-mismatch",
                    message=(
                        f"{location}: Service targetPort '{target}' doesn't match any "
                        "container port name."
                    ),
                    severity=Severity.CRITICAL,
                )
            )

    return tuple(findings)


def _check_secret_example_placeholders(
    docs_by_path: dict[Path, list[Any]], output_dir: Path
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    for path, docs in docs_by_path.items():
        if path.name != "secret.example.yaml":
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            for key, value in (doc.get("stringData") or {}).items():
                if value != SECRET_PLACEHOLDER_VALUE:
                    findings.append(
                        Finding(
                            code="manifest-secret-example-not-placeholder",
                            message=(
                                f"{path.relative_to(output_dir)}: key '{key}' is not the "
                                f"placeholder value '{SECRET_PLACEHOLDER_VALUE}'."
                            ),
                            severity=Severity.CRITICAL,
                        )
                    )
    return tuple(findings)
