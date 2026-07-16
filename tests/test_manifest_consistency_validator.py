from __future__ import annotations

from pathlib import Path

from gitops_scaffold.validators.manifests import ManifestConsistencyValidator

_VALID_DEPLOYMENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: web
  template:
    metadata:
      labels:
        app.kubernetes.io/name: web
    spec:
      containers:
        - name: web
          image: x:1.0
          ports:
            - name: tcp-80
              containerPort: 80
          volumeMounts:
            - name: web-data
              mountPath: /data
      volumes:
        - name: web-data
          persistentVolumeClaim:
            claimName: web-data
"""

_VALID_SERVICE = """
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app.kubernetes.io/name: web
  ports:
    - name: tcp-80
      port: 80
      targetPort: tcp-80
"""

_VALID_PVC = """
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: web-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
"""

_VALID_KUSTOMIZATION = """
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
  - pvc.yaml
"""


def _write(directory: Path, name: str, content: str) -> None:
    (directory / name).write_text(content)


def test_valid_directory_produces_no_findings(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", _VALID_DEPLOYMENT)
    _write(tmp_path, "service.yaml", _VALID_SERVICE)
    _write(tmp_path, "pvc.yaml", _VALID_PVC)
    _write(tmp_path, "kustomization.yaml", _VALID_KUSTOMIZATION)

    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert findings == ()


def test_invalid_yaml_syntax_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", "not: valid: yaml: [")
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-invalid-yaml" for f in findings)


def test_missing_metadata_name_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", "apiVersion: apps/v1\nkind: Deployment\nmetadata: {}\n")
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-missing-name" for f in findings)


def test_invalid_resource_name_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "deployment.yaml",
        "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: Invalid_Name\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-invalid-name" for f in findings)


def test_kustomization_missing_resource_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "kustomization.yaml",
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - missing.yaml\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-missing-kustomization-resource" for f in findings)


def test_kustomization_directory_reference_is_valid(tmp_path: Path) -> None:
    (tmp_path / "web").mkdir()
    _write(
        tmp_path / "web",
        "kustomization.yaml",
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources: []\n",
    )
    _write(
        tmp_path,
        "kustomization.yaml",
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - web\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert not any(f.code == "manifest-missing-kustomization-resource" for f in findings)


def test_kustomization_forbidden_resource_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "secret.example.yaml",
        "apiVersion: v1\nkind: Secret\nmetadata:\n  name: web-secret\nstringData:\n  X: CHANGE_ME\n",
    )
    _write(
        tmp_path,
        "kustomization.yaml",
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n  - secret.example.yaml\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-forbidden-kustomization-resource" for f in findings)


def test_selector_mismatch_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", _VALID_DEPLOYMENT)
    bad_service = _VALID_SERVICE.replace(
        "app.kubernetes.io/name: web", "app.kubernetes.io/name: other"
    )
    _write(tmp_path, "service.yaml", bad_service)
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-selector-mismatch" for f in findings)


def test_targetport_mismatch_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", _VALID_DEPLOYMENT)
    bad_service = _VALID_SERVICE.replace("targetPort: tcp-80", "targetPort: nonexistent")
    _write(tmp_path, "service.yaml", bad_service)
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-targetport-mismatch" for f in findings)


def test_volume_mount_mismatch_flagged(tmp_path: Path) -> None:
    bad_deployment = _VALID_DEPLOYMENT.replace(
        "      volumes:\n        - name: web-data\n          persistentVolumeClaim:\n            claimName: web-data\n",
        "",
    )
    _write(tmp_path, "deployment.yaml", bad_deployment)
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-volume-mount-mismatch" for f in findings)


def test_pvc_reference_missing_flagged(tmp_path: Path) -> None:
    _write(tmp_path, "deployment.yaml", _VALID_DEPLOYMENT)
    # No pvc.yaml at all -- claimName references nothing.
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-pvc-reference-missing" for f in findings)


def test_secret_example_non_placeholder_value_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "secret.example.yaml",
        "apiVersion: v1\nkind: Secret\nmetadata:\n  name: web-secret\nstringData:\n  API_TOKEN: not-the-placeholder\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-secret-example-not-placeholder" for f in findings)


def test_redaction_marker_leak_flagged(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "configmap.yaml",
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: web-config\ndata:\n  FOO: '***REDACTED***'\n",
    )
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert any(f.code == "manifest-redaction-leak" for f in findings)


def test_multi_document_pvc_yaml_parses(tmp_path: Path) -> None:
    multi_pvc = _VALID_PVC + "---\n" + _VALID_PVC.replace("web-data", "web-data-2")
    _write(tmp_path, "pvc.yaml", multi_pvc)
    findings = ManifestConsistencyValidator().validate(tmp_path)
    assert not any(f.code == "manifest-invalid-yaml" for f in findings)
