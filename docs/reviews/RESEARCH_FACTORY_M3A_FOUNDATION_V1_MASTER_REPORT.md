# Research Factory M3A Foundation V1 — Master Report

**Verdict:** `M3A_RESEARCH_FACTORY_FOUNDATION_COMPLETE_WITH_WARNINGS`  
**Not:** Milestone 3 complete.

## Delivered

- Hypothesis / Evidence / Experiment registries (`im.research.*.v1`)
- Append-only Learning Memory
- Deterministic Information Value (not expected-profit-only)
- Manual approval gate (`PRE_REGISTERED` → `MANUALLY_APPROVED` only)
- Seed import: M2 n=6 → **INCONCLUSIVE / INSUFFICIENT_SAMPLE** (not anti-edge)
- APIs under `/api/v1/research/*` (separate from Stage 3 epistemic routes)
- SDK methods
- `auto_run=false`, `promotion_eligible=false`, `live_policy_influence=false`

## Warnings

- Seed evidence is static/report-backed, not a live prospective sample
- Agents may propose DRAFT only
- No autonomous experiment execution

## Storage

`data/research_factory_m3a/` (gitignored runtime)
