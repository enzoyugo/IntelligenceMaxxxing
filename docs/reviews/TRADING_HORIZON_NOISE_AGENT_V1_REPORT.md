# TRADING_HORIZON_NOISE_AGENT_V1

Agent: `HorizonNoiseAgentV1@1.0.0`  
Schema: `im.trading.horizon_noise_assessment.v1`

- `non_authoritative=true`, `live_control=false`, `decision=null`
- Outside frozen `IM_M2_AGENT_BUNDLE@1.0.0` (bundle hash untouched)
- Policy `IM_TRADING_DECISION_POLICY@1.0.0` untouched
- Always `NO_TRUSTED_PRIOR` when only diagnostic N=33 prior exists
- No TAKE/SKIP; does not mutate IM_ADVISORY
- API: `POST/GET /api/v1/trading/horizon-noise-assessments`
