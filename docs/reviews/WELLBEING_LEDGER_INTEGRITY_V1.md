# WELLBEING LEDGER INTEGRITY V1

## Principles

1. Ledger is append-only.  
2. Corrections are additive exclusions / superseding events — never silent edits.  
3. Historical snapshots are never overwritten.  
4. Test data must not share the personal production database for smokes.

## Counts (this session)

| Question | Answer |
|----------|--------|
| How many observations exist? | Live total unavailable (Postgres down) |
| How many personal? | Live unavailable; policy classifies LifeOS personal URIs as PERSONAL_PRODUCTION when eligible |
| How many test? | ≥1 known (`obs_ab746ef9…`) plus any matching smoke source prefixes |
| How many invalidated? | ≥1 (bootstrap exclusion) |
| Snapshots affected? | Those computed under old policy including the smoke day |
| New snapshots? | Created on next productive compute with `wellbeing_input_selection_v1` |
| Did current score change? | Expected: smoke day removed from effective inputs → yes if it previously contributed |

## Fingerprints

New snapshots carry a new input fingerprint reflecting the corrected effective set. Old fingerprints remain on historical rows.

## Payload privacy

This report does not publish full personal check-in payloads.
