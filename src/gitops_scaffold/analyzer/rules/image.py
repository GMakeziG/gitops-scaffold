"""Flags image reference hygiene: missing image, no tag, ``:latest``, unpinned.

A 9th detection rule beyond the original eight — reproducibility/supply-chain
hygiene for image references doesn't fit any of the other eight modules'
single concern, and folding it into ``security.py`` would blur that module's
"isolation risk" focus. See ``docs/roadmap.md``/``docs/compose-support.md``.
"""

from __future__ import annotations

from gitops_scaffold.analyzer.rules.base import DetectionRule
from gitops_scaffold.models.analysis import Finding, Severity
from gitops_scaffold.models.app import ServiceDefinition


def _split_image_reference(image: str) -> tuple[str, str | None, bool]:
    """Returns ``(repository, tag, pinned_by_digest)``."""
    if "@" in image:
        repo, _, _digest = image.partition("@")
        return repo, None, True

    # A tag is only the part after the LAST ':' if that colon comes after the
    # last '/' — otherwise it's a registry port, e.g. "localhost:5000/app".
    last_slash = image.rfind("/")
    last_colon = image.rfind(":")
    if last_colon > last_slash:
        repo, _, tag = image.rpartition(":")
        return repo, tag, False
    return image, None, False


class ImageTagDetectionRule(DetectionRule):
    code = "image"

    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        if service.image is None:
            return (
                Finding(
                    code="image-missing",
                    message=(
                        f"Service '{service.name}' has no image (build-only services "
                        "aren't analyzed in v0.2)."
                    ),
                    severity=Severity.CRITICAL,
                    service_name=service.name,
                    field_path="image",
                    remediation="Provide an 'image:' reference, or wait for build-context support.",
                ),
            )

        repo, tag, pinned_by_digest = _split_image_reference(service.image)

        if pinned_by_digest:
            return (
                Finding(
                    code="image-pinned-digest",
                    message=f"Service '{service.name}' image is pinned by digest: {service.image}",
                    severity=Severity.INFO,
                    service_name=service.name,
                    field_path="image",
                ),
            )

        if tag is None:
            return (
                Finding(
                    code="image-tag-missing",
                    message=(
                        f"Service '{service.name}' image '{repo}' has no explicit tag "
                        "(defaults to :latest)."
                    ),
                    severity=Severity.WARNING,
                    service_name=service.name,
                    field_path="image",
                    remediation="Pin an explicit version tag for reproducible deployments.",
                ),
            )

        if tag == "latest":
            return (
                Finding(
                    code="image-tag-latest",
                    message=(
                        f"Service '{service.name}' image is explicitly pinned to ':latest' "
                        "— not reproducible."
                    ),
                    severity=Severity.WARNING,
                    service_name=service.name,
                    field_path="image",
                    remediation="Pin a specific version tag instead of 'latest'.",
                ),
            )

        return (
            Finding(
                code="image-tag-pinned",
                message=f"Service '{service.name}' image detected: {service.image}",
                severity=Severity.INFO,
                service_name=service.name,
                field_path="image",
            ),
        )
