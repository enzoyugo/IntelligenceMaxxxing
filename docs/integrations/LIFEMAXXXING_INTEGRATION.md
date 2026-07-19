# LifeMaxxxing integration (Stage 2)

LifeMaxxxing is the first external client application of the IntelligenceMaxxxing
Engine. This document records the integration architecture from the **Engine's**
perspective. The Engine contains no LifeMaxxxing-specific logic: LifeMaxxxing is
just a registered Application submitting `life`-namespaced observations through
the public contract.

## Topology

```
Expo app (device)
   │  HTTP, no Engine credential
   ▼
LifeMaxxxing backend  (FastAPI, /api/intelligence/*)
   │  standalone SDK (intelligence_maxxxing_client) over public HTTP
   ▼
Engine public API  (/api/v1, Bearer credential, idempotency keys)
   │
   ▼
PostgreSQL append-only ledger (audits, integrity chain, projections)
```

Forbidden paths (enforced by architecture + gates):
- Expo never calls the Engine or PostgreSQL directly.
- LifeMaxxxing never imports the Engine Core (`intelligence_maxxxing`); it uses
  only the standalone `intelligence_maxxxing_client` wheel (httpx + pydantic).
- The Engine never imports the SDK or any application code (import-linter).

## What the Engine sees

- `domain_pack="life"` observations with subjects `daily_check_in` and `workout`.
- `context.attributes`: minimized structured metrics only (scores, hours, counts).
  LifeMaxxxing's registry guarantees free text (notes, wins, blockers, exercise
  names) never crosses the boundary — E2E canaries assert this against the ledger.
- `metadata.life_event_type`: the registered Life event type
  (`life.daily_check_in.completed.v1`, `life.workout.completed.v1`).
- Idempotency keys derived deterministically on-device
  (`life-<event_type>-<entity>-<payload_hash>`), so retries replay instead of
  duplicating.

## Identity and permissions

LifeMaxxxing is registered via the governed local CLI with the minimal scope
profile:

| Scope | Why |
|---|---|
| `SUBMIT_OBSERVATION` | submit minimized observations |
| `READ_AUDIT` | recover audit records for stored receipts |
| `READ_INTELLIGENCE` | read its own observations/projections |

No administration, execution or domain-pack scopes. The credential secret lives
only in the LifeMaxxxing backend's gitignored `.env.server` (runbook:
`docs/INTELLIGENCE_ENGINE_CREDENTIAL_SETUP.md` in the LifeMaxxxing repo).

## Compatibility lock

`docs/integrations/lifemaxxxing_compatibility_lock.json` pins the contract both
sides were certified against (API version, SDK version, event types, scopes,
error codes). Regenerate/review it whenever either side changes the contract,
and re-run the cross-repo gate.

## Cross-repo gate

```powershell
powershell -ExecutionPolicy Bypass -File scripts\audit\run_lifemaxxxing_contract_gates.ps1
```

Runs on real PostgreSQL and real HTTP servers: SDK wheel certification, fresh
E2E database, CLI-provisioned identities, LifeMaxxxing backend suite, 27 online
canaries (sync, replay, minimization, audits, typed errors, cross-app
isolation), 6 offline canaries (Engine down), and a secret scan of the
LifeMaxxxing repo. Optionally set `LIFEMAXXXING_ROOT` if the Life repo is not at
its default location.
