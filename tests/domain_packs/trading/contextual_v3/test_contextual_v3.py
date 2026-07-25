from intelligence_maxxxing.domain_packs.trading.contextual_v3 import (
    LIVE_POLICY_INFLUENCE,
    PROMOTION_ELIGIBLE,
    RESEARCH_POLICY_ID,
)


def test_contextual_v3_not_live():
    assert PROMOTION_ELIGIBLE is False
    assert LIVE_POLICY_INFLUENCE is False
    assert "V3" in RESEARCH_POLICY_ID
