"""Domain Pack placeholders must never pretend to work (Stage 0 honesty rule)."""

import pytest

from intelligence_maxxxing.domain_packs.base import (
    CapabilityNotImplementedYet,
    DomainPackContract,
)
from intelligence_maxxxing.domain_packs.life import LifePackPlaceholder


def test_life_pack_placeholder_never_simulates_capabilities() -> None:
    pack = LifePackPlaceholder()
    capability_names = [
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
    ]
    for name in capability_names:
        with pytest.raises(CapabilityNotImplementedYet):
            getattr(pack, name)()


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
