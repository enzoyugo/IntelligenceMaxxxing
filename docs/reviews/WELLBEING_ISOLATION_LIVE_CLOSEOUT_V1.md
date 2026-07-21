# WELLBEING ISOLATION LIVE CLOSEOUT V1

## Database identity

| Field | Value |
|-------|-------|
| Database name | `intelligence_maxxxing` |
| Host:port | `127.0.0.1:5432` |
| Fingerprint | `81ab3f598f01ff2c` |
| Migration | `0008_observation_exclusion` (head) |
| Personal? | yes (default name) |

## Durable exclusion

Table `observation_exclusions` seeded for smoke obs. Process cache + extractors consume it.

## Engine fix in closeout

`WellbeingService.get_current` now returns merged `features` including `input_selection_policy_version` (was persisted but omitted from response).

## Operational proofs

1. Isolated smoke PASS — zero personal ledger delta  
2. Live correction PRESENT + effective excluded  
3. New V1/V2 snapshot IDs with exclusion counts  
4. Historical snapshots retained  

## iPhone Daily Flow

Pending device run this session — see LifeOS reports / master warnings.
