"""The detection rule interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gitops_scaffold.models.analysis import Finding
from gitops_scaffold.models.app import ServiceDefinition


class DetectionRule(ABC):
    """A single, narrowly-scoped detection concern.

    Implementations should be pure functions of their input service — no I/O,
    no shared mutable state — so they're trivial to unit test in isolation.
    """

    #: A stable identifier prefix for findings this rule produces,
    #: e.g. ``"health-check"``. Individual findings may suffix this
    #: (e.g. ``"health-check-missing"``).
    code: str

    @abstractmethod
    def check(self, service: ServiceDefinition) -> tuple[Finding, ...]:
        raise NotImplementedError
