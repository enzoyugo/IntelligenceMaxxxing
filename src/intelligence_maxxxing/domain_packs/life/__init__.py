"""Life Pack v0.1.0 — EXPERIMENTAL / SHADOW.

Real Stage 3 logic lives in eligibility.py, learning_templates.py, and
methods/bayesian_bootstrap.py. The pack never accesses tables directly;
callers use Core ports. Autonomy ceiling: OBSERVE / ANALYZE / EXPLAIN.
"""

from intelligence_maxxxing.domain_packs.base import (
    CapabilityNotApplicable,
    CapabilityNotImplementedYet,
    DomainPackContract,
    PackStatus,
)


class LifePack(DomainPackContract):
    """Shadow Life Pack admitted for the first epistemic loop."""

    name = "life"
    version = "0.1.0"
    status = PackStatus.EXPERIMENTAL

    def observe(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.observe is performed by external clients via the public API"
        )

    def normalize(self) -> None:
        raise CapabilityNotImplementedYet("life.normalize is not yet a pack entrypoint")

    def validate(self) -> None:
        raise CapabilityNotImplementedYet("life.validate is not yet a pack entrypoint")

    def generate_hypotheses(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.generate_hypotheses is human-driven via public hypothesis APIs"
        )

    def design_experiment(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.design_experiment is pre-registered at hypothesis activation"
        )

    def evaluate_evidence(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.evaluate_evidence runs through governed experiments.evaluate"
        )

    def calibrate_confidence(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.calibrate_confidence remains UNCALIBRATED in Stage 3"
        )

    def recommend(self) -> None:
        raise CapabilityNotApplicable("life.recommend is forbidden (autonomy ceiling)")

    def evaluate_outcome(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.evaluate_outcome runs inside governed experiments.evaluate"
        )

    def learn(self) -> None:
        raise CapabilityNotImplementedYet(
            "life.learn uses deterministic templates inside experiments.evaluate"
        )

    def health_check(self) -> None:
        raise CapabilityNotImplementedYet("life.health_check is not yet a pack entrypoint")


# Backward-compatible alias for older imports.
LifePackPlaceholder = LifePack
