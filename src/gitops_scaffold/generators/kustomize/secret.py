"""Generates ``secret.example.yaml`` placeholders — never real ``Secret`` objects.

This generator must never write a real Kubernetes ``Secret`` containing
plaintext (or redacted) values — it never even reads ``EnvVar.value`` for a
secret-shaped variable, only its name and the finding code that classified
it (see ``generators/secret_classification.py``). Every value it renders is
the fixed placeholder ``"CHANGE_ME"``. Renders
``templates/secret.example.yaml.j2``.
"""

from __future__ import annotations

from dataclasses import dataclass

from gitops_scaffold.config.settings import ScaffoldSettings
from gitops_scaffold.generators.base import ManifestGenerator
from gitops_scaffold.generators.labels import standard_labels
from gitops_scaffold.generators.layout import resource_path
from gitops_scaffold.generators.rendering import render_template
from gitops_scaffold.generators.secret_classification import (
    has_env_file_reference,
    is_optional,
    secret_classifications,
)
from gitops_scaffold.models.analysis import AnalysisResult
from gitops_scaffold.models.app import ApplicationDefinition
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.utils.naming import k8s_resource_name


@dataclass(frozen=True)
class _SecretKey:
    name: str
    optional: bool


class SecretExampleGenerator(ManifestGenerator):
    kind = "SecretExample"

    def __init__(self, settings: ScaffoldSettings | None = None) -> None:
        self._settings = settings or ScaffoldSettings()

    def generate(self, app: ApplicationDefinition, analysis: AnalysisResult) -> GenerationOutcome:
        files: list[GeneratedFile] = []
        notes: list[GenerationNote] = []
        total_services = len(app.services)

        for service in app.services:
            classifications = secret_classifications(service.name, analysis)

            if classifications:
                resource_name = k8s_resource_name(service.name, "secret")
                keys = [
                    _SecretKey(name=var_name, optional=is_optional(code))
                    for var_name, code in sorted(classifications.items())
                ]
                content = render_template(
                    "secret.example.yaml.j2",
                    resource_name=resource_name,
                    namespace=self._settings.default_namespace,
                    labels=standard_labels(service, app, self._settings),
                    keys=keys,
                )
                files.append(
                    GeneratedFile(
                        relative_path=resource_path(
                            service.name, "secret.example.yaml", total_services
                        ),
                        content=content,
                        requires_review=True,
                    )
                )

                required = [key.name for key in keys if not key.optional]
                optional = [key.name for key in keys if key.optional]
                message = (
                    f"Service '{service.name}' expects a live Secret named '{resource_name}' "
                    f"— the Deployment will not become Ready until it exists. Required keys: "
                    f"{', '.join(required) or 'none'}. Optional keys: {', '.join(optional) or 'none'}."
                )
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.WARNING,
                        message=message,
                        service_name=service.name,
                        requires_review=True,
                    )
                )

            if has_env_file_reference(service.name, analysis):
                notes.append(
                    GenerationNote(
                        category=GenerationNoteCategory.ASSUMPTION,
                        message=(
                            f"Service '{service.name}' references an env_file — its contents "
                            "were not inspected; populate any secrets it defines manually."
                        ),
                        service_name=service.name,
                        requires_review=True,
                    )
                )

        return GenerationOutcome(files=tuple(files), notes=tuple(notes))
