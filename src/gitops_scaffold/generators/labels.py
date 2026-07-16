"""Shared label-building — the single source of truth for Deployment pod
labels and Service selectors, so the two can never drift apart.

Every generator that needs labels calls these two functions instead of
building label dicts inline, which is what guarantees "Service selector
exactly matches Deployment pod labels" structurally rather than by
convention.
"""

from __future__ import annotations

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition
from gitops_scaffold.utils.naming import kebab_case


def pod_selector_labels(service: ServiceDefinition, app: ApplicationDefinition) -> dict[str, str]:
    """The minimal, stable label set used for Deployment matchLabels *and* Service selectors.

    Deliberately excludes ``settings.additional_labels`` — selectors should
    be based only on identity that never changes across a Deployment's
    lifetime; user-configured extra labels are free to change without
    requiring a Deployment replacement.
    """
    return {
        "app.kubernetes.io/name": kebab_case(service.name),
        "app.kubernetes.io/part-of": kebab_case(app.name),
    }


def standard_labels(
    service: ServiceDefinition, app: ApplicationDefinition, settings: ScaffoldSettings
) -> dict[str, str]:
    """The full label set applied to every generated resource's ``metadata.labels``.

    A superset of :func:`pod_selector_labels` — safe, since Kubernetes only
    requires ``matchLabels``/selectors to be a *subset* of the actual labels.
    """
    labels = {
        **pod_selector_labels(service, app),
        "app.kubernetes.io/managed-by": "gitops-scaffold",
    }
    labels.update(settings.additional_labels)
    return labels
