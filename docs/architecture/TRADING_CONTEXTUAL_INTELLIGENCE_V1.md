# Trading Contextual Intelligence V1

- No TMX storage reads from IM process internals for economics.
- Assessments must carry `decision_source`, `model_hash`, `feature_registry_hash`.
- Alias lanes with identical decisions must be labelled `LANES_IDENTICAL_NOT_DISTINCT_EXPERIMENTS`.
- Missing PIT sources stay UNKNOWN; never invent news/quotes.
