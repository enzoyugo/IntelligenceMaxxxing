"""Minimum capability contract for Domain Packs (DOMAIN_PACK_STANDARD.md §6).

Stage 0 defines the interface only. Each capability must eventually be
implemented or explicitly declared non-applicable. Raising the typed
exceptions below is the honest placeholder behavior: a pack can never
pretend a capability works before it exists.
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class PackStatus(StrEnum):
    EXPERIMENTAL = "EXPERIMENTAL"
    OFFICIAL = "OFFICIAL"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class CapabilityNotImplementedYet(Exception):
    """The capability is planned but does not exist yet. Never simulated."""


class CapabilityNotApplicable(Exception):
    """The pack explicitly declares this capability non-applicable."""


class DomainPackContract(ABC):
    """Every Domain Pack implements or explicitly declines these capabilities.

    Packs never duplicate Core universal objects, never access another pack's
    tables, and never modify another pack's objects (protected by tests).
    """

    name: str
    version: str
    status: PackStatus

    @abstractmethod
    def observe(self) -> None: ...

    @abstractmethod
    def normalize(self) -> None: ...

    @abstractmethod
    def validate(self) -> None: ...

    @abstractmethod
    def generate_hypotheses(self) -> None: ...

    @abstractmethod
    def design_experiment(self) -> None: ...

    @abstractmethod
    def evaluate_evidence(self) -> None: ...

    @abstractmethod
    def calibrate_confidence(self) -> None: ...

    @abstractmethod
    def recommend(self) -> None: ...

    @abstractmethod
    def evaluate_outcome(self) -> None: ...

    @abstractmethod
    def learn(self) -> None: ...

    @abstractmethod
    def health_check(self) -> None: ...
