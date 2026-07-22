# Research Evidence Bundle V1 Report

**Verdict:** `M3B_EVIDENCE_BUNDLE_CONTRACT_FOUNDATION_COMPLETE`  
**Schema:** `im.research.evidence_bundle.v1`

## Contract fields

- `bundle_id`, `schema_version`, `m3b_id`, `m3b_version`
- `subject_refs`, `items[]` (source_kind/ref, direction, summary, labels)
- `trust_status` ∈ TRUSTED / PARTIAL / CONFLICTED / MISSING_EVIDENCE / PENDING_OUTCOME / DATA_QUALITY_BLOCKED / FIXTURE_ONLY / UNTRUSTED
- `temporal_label`, `origin_label`
- `coverage` counts by direction + missing kinds
- `limitations`, `input_hash`, `output_hash` / `content_hash`
- Flags: `non_authoritative`, `append_only`, `research_only`, `live_control=false`

## Storage

- JSONL: `data/research_factory_m3b/evidence_bundles.jsonl`
- Env override: `IM_RESEARCH_M3B_STORE_DIR`
- Idempotent by `output_hash` (skip duplicate append)

## API

- `GET/POST /api/v1/research/evidence-bundles`
- `GET /api/v1/research/evidence-bundles/{id}`
