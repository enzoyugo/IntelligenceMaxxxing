# Research Evidence Agent V1 Report

**Verdict:** `M3B_EVIDENCE_AGENT_FOUNDATION_COMPLETE`  
**Not:** Milestone 3 complete / authoritative evidence.

## Scope

- Agent: `EvidenceAgentV1` (`IM_RESEARCH_FACTORY_M3B` / `1.0.0`)
- Schema: `im.research.evidence_bundle.v1`
- Mode: deterministic, read-only, non-authoritative, append-only

## Behavior

- Builds bundles only from provided subject refs (observation, assessment, context, anomaly, critic, shadow, cost, registry_evidence, reports, outcome_ref).
- Never invents evidence items.
- Classifies items as `SUPPORTING` / `CONTRADICTING` / `NEUTRAL` / `DATA_QUALITY` / `PENDING_OUTCOME`.
- Rejects forbidden outcome fields on pre-outcome surfaces via `has_forbidden_outcome_fields`.
- Outcome refs allowed only after `cutoff_utc`, labeled `PENDING_OUTCOME` (not for pre-outcome decisioning).
- Labels temporal (`PROSPECTIVE` / `RETROSPECTIVE`) and origin (`REAL` / `FIXTURE` / `MIXED`).

## Safety

- `non_authoritative=true`, `append_only=true`, `live_control=false`, `promotion_eligible=false`
- No broker, no TMX storage, no Ollama, no policy mutation
