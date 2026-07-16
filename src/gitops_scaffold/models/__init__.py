"""The normalized intermediate representation (IR) used throughout gitops-scaffold.

Every input format (Docker Compose today; Dockerfiles, Helm charts, plain
Kubernetes manifests, and GitHub repositories are stubbed for future
milestones — see ``parsers/``) is parsed into an
:class:`~gitops_scaffold.models.app.ApplicationDefinition`. Analyzers,
generators, and validators only ever operate on this IR — they never need to
know what format the application definition originally came from.
"""

from __future__ import annotations

from gitops_scaffold.models.analysis import AnalysisResult, Finding, Severity
from gitops_scaffold.models.app import (
    ApplicationDefinition,
    EnvVar,
    HealthCheck,
    PortMapping,
    Protocol,
    ResourceRequirements,
    RuntimeUser,
    ServiceDefinition,
    VolumeMount,
)
from gitops_scaffold.models.generation import (
    GeneratedFile,
    GenerationNote,
    GenerationNoteCategory,
    GenerationOutcome,
)
from gitops_scaffold.models.generation_report import GenerationReport
from gitops_scaffold.models.report import AnalysisReport

__all__ = [
    "AnalysisReport",
    "AnalysisResult",
    "ApplicationDefinition",
    "EnvVar",
    "Finding",
    "GeneratedFile",
    "GenerationNote",
    "GenerationNoteCategory",
    "GenerationOutcome",
    "GenerationReport",
    "HealthCheck",
    "PortMapping",
    "Protocol",
    "ResourceRequirements",
    "RuntimeUser",
    "ServiceDefinition",
    "Severity",
    "VolumeMount",
]
