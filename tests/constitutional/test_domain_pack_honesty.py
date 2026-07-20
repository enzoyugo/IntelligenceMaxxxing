"""Domain Pack honesty: unimplemented raises typed errors; recommend is N/A."""

import pytest

from intelligence_maxxxing.domain_packs.base import (
    CapabilityNotApplicable,
    CapabilityNotImplementedYet,
    DomainPackContract,
)
from intelligence_maxxxing.domain_packs.life import LifePackPlaceholder


def test_life_pack_placeholder_never_simulates_capabilities() -> None:
    pack = LifePackPlaceholder()
    unimplemented = [
        "observe",
        "normalize",
        "validate",
        "generate_hypotheses",
        "design_experiment",
        "evaluate_evidence",
        "calibrate_confidence",
        "evaluate_outcome",
        "learn",
        "health_check",
    ]
    for name in unimplemented:
        with pytest.raises(CapabilityNotImplementedYet):
            getattr(pack, name)()
    with pytest.raises(CapabilityNotApplicable):
        pack.recommend()


def test_pack_contract_declares_all_required_capabilities() -> None:
    required = {
        "observe",
        "normalize",
        "validate",
        "generate_hypotheses",
        "design_experiment",
        "evaluate_evidence",
        "calibrate_confidence",
        "recommend",
        "evaluate_outcome",
        "learn",
        "health_check",
    }
    abstract = set(getattr(DomainPackContract, "__abstractmethods__", set()))
    assert required <= abstract
