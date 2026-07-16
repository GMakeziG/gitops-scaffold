"""Generates the Kubernetes ``ConfigMap`` manifest for non-secret environment variables.

Renders ``templates/configmap.yaml.j2``. Secret-classified variables (per
``generators/secret_classification.py``, derived from analysis findings, not
re-derived here) are excluded entirely — they belong in
``secret.example.yaml`` instead. No ConfigMap is generated for a service
with zero non-secret variables.
"""

from __future__ import annotations

from dataclasses import dataclass

from gitops_scaffold.analyzer.rules.secrets import INTERPOLATION_PATTERN
from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.labels import standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.generators.secret_classification import secret_classifications
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition, ServiceDefinition
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.utils.naming import k8s_resource_name


@dataclass(frozen=True)
class _ConfigVar:
    name: str
    value: str
    review_reason: str | None = None

    @property
    def requires_review(self) -> bool:
        return self.review_reason is not None


class ConfigMapGenerator(ManifestGenerator):
    kind = "ConfigMap"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files: list[GeneratedFile] = []
        notes: list[GenerationNote] = []
        total_services = len(app.services)

        for service in app.services:
            secret_names = secret_classifications(service.name, analysis)
            if not has_configmap_data(service, secret_names):
                continue
            config_vars = [
                _build_config_var(var.name, var.value)
                for var in service.environment
                if var.name not in secret_names
            ]

            resource_name = k8s_resource_name(service.name, "config")
            content = render_template(
                "configmap.yaml.j2",
                resource_name=resource_name,
                namespace=self._settings.default_namespace,
                labels=standard_labels(service, app, self._settings),
                config_vars=config_vars,
            )
            requires_review = any(var.requires_review for var in config_vars)
            files.append(
                GeneratedFile(
                    relative_path=resource_path(service.name, "configmap.yaml", total_services),
                    content=content,
                    requires_review=requires_review,
                )
            )

            notes.extend(
                GenerationNote(
                    category=GenerationNoteCategory.ASSUMPTION,
                    message=(
                        f"ConfigMap value '{var.name}' for service '{service.name}' needs "
                        f"review: {var.review_reason}."
                    ),
                    service_name=service.name,
                    requires_review=True,
                )
                for var in config_vars
                if var.requires_review
            )

        return GenerationOutcome(files=tuple(files), notes=tuple(notes))


def has_configmap_data(service: ServiceDefinition, secret_names: dict[str, str]) -> bool:
    """Whether ``service`` has at least one non-secret environment variable.

    Shared with :class:`~gitops_scaffold.generators.kustomize.deployment.DeploymentGenerator`,
    which needs the identical predicate to decide whether to reference this
    ConfigMap via ``envFrom`` — reusing this function (rather than each
    generator re-deriving its own copy) is what guarantees they can never
    disagree about whether a ConfigMap exists for a given service.
    """
    return any(var.name not in secret_names for var in service.environment)


def _build_config_var(name: str, value: str | None) -> _ConfigVar:
    if value is None:
        return _ConfigVar(
            name=name,
            value="",
            review_reason=(
                "no value written in the Compose file — sourced from the shell "
                "environment running Compose"
            ),
        )
    if INTERPOLATION_PATTERN.match(value):
        return _ConfigVar(
            name=name,
            value=value,
            review_reason=(
                "this was Compose variable interpolation — Kubernetes won't expand it; "
                "confirm the resolved value"
            ),
        )
    return _ConfigVar(name=name, value=value)
