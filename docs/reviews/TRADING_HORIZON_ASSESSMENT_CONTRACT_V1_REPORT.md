# TRADING_HORIZON_ASSESSMENT_CONTRACT_V1

Contract: `im.trading.horizon_noise_assessment.v1`

Output fields: expected_horizon_class, noise_exposure, entry_quality, breakout_quality, stop_robustness, cost_sensitivity, reason_codes, evidence_refs, limitations, confidence, hashes.

Forbidden: TAKE/SKIP, outcome access, live control, policy threshold emission, promotion.

Storage: append-only `trading_horizon_noise_assessments.jsonl` under IM trading store.
