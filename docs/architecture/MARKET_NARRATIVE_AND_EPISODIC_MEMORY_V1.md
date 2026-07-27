# Market Narrative and Episodic Memory V1

## Narrative object

Required (schema): `narrative_id`, `symbol`, `as_of`, `available_at`, structure/liquidity/zone/regime/event-risk summaries, `evidence_object_ids`, `uncertainty`, `narrative_hash`.

Outcomes are forbidden at decision time.

## Hypothesis object

States: `CREATED`, `ACTIVE`, `SUPPORTED`, `CONTRADICTED`, `INVALIDATED`, `EXPIRED`.

Must bind invalidation conditions and evidence links to TMX object IDs with causal timestamps.

## Episodic memory

Store id: `TMX_IM_EPISODIC_MARKET_MEMORY_V1`

Retrieval keys: structure template, liquidity path, zone lifecycle, session, volatility.

Outcome labels are stored separately from retrieval keys used at decision time.

## Authority

IM owns narrative/hypothesis/episodic assessment. TMX owns market objects, safety, execution, and portfolio hard constraints.
