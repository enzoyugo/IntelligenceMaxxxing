# Trading Family Contextual Policy Adjudication V1

## Scope

Research-only adjudication of frozen TMX PIT contextual family candidates.
Policy IM **1.0.0** and M2 Bundle **1.0.0** are **unchanged**.

## Verdict (TMX campaign authority)

`FAMILY_EDGE_ADJUDICATION_COMPLETE_VALID_NEAR_MISS`

| Candidate | Classification |
|-----------|----------------|
| IM_CONTEXT_FAMILY | VALID_CONTEXTUAL_NEAR_MISS |
| TMX_MARKET_PLUS_IM | REJECT_CELL_CONCENTRATION |
| TMX_PORTFOLIO_PLUS_IM | REJECT_CELL_CONCENTRATION |

## IM implications

- Family-scoped ridge decisions remain research-only; not promoted to live policy.
- Fallback tracking on replay: all FAMILY eval rows used `family_model_trained` (no silent global fallback).
- Assessment / enrollment / bridge paths must continue to ignore these research artifacts for live control.
- No threshold retune, no feature addition, no Policy version bump from this sprint.

## Provenance

- TMX baseline HEAD at adjudication start: `0f9093e…`
- IM baseline HEAD: `f4ac889…`
- OOS rows read: 0; forward training rows: 0

## Next

Do not bind FAMILY near-miss into Policy IM. If a future shadow sprint is designed, keep Policy/M2 frozen and isolate research assessments.
