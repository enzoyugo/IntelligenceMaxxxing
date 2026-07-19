# Stage 2 report: LifeMaxxxing external client, offline outbox and audited observation sync

**Verdict: STAGE_2_COMPLETE.** The first real vertical slice works end-to-end and
is gated: a LifeMaxxxing record saved locally produces an immutable outbox item,
the LifeMaxxxing backend validates and minimizes it, the standalone SDK submits
it to `POST /api/v1/observations`, the Engine returns `observation_id` /
`event_id` / `audit_id`, LifeMaxxxing stores the receipt, and the audit is
recoverable through the Life backend.

## Roots

| Repo | Root | Baseline |
|---|---|---|
| Engine | `E:\IntelligenceMaxxxing` (branch `main`) | `775a31d` |
| LifeMaxxxing | `C:\Users\AORUS\lifeos-maxxxing` (branch `master`, no remote) | `a04b3b3` |

LifeMaxxxing root was validated (Expo app with expo-router/expo-sqlite in
`app/`+`lib/`, FastAPI backend in `src/server/app.py` + `src/brain/`), exactly
one candidate — no ambiguity verdict needed.

## Commits

Engine:
- `775a31d` STAGE_2_BASELINE — trusted Engine frozen.
- `3212d4c` STAGE_2_SDK — standalone `intelligence-maxxxing-client` package
  (`sdk/python/pyproject.toml`, httpx+pydantic only, Python >=3.10), build/test
  scripts, hermetic SDK unit tests, Engine-side certification tests (7) incl.
  wheel-contains-no-Core and minimal-scope profile.
- `33d723a` STAGE_2_CONTRACT — `run_lifemaxxxing_contract_gates.ps1` + E2E
  canary driver.
- (this commit) STAGE_2_REPORT — integration docs, compatibility lock, report.

LifeMaxxxing:
- `a04b3b3` STAGE_2_BASELINE.
- `f86c545` STAGE_2_BACKEND_ADAPTER — `src/intelligence/` package (server-only
  config reading gitignored `.env.server`, event-type registry with hard data
  minimization, adapter over the standalone SDK, `/api/intelligence/*` router),
  15 hermetic unittest cases, credential runbook.
- `0b1cace` STAGE_2_OFFLINE_OUTBOX — SQLite schema v9 (`intelligence_outbox`,
  `intelligence_sync_settings`), on-device minimization, deterministic
  idempotency keys, sync worker (backoff, IN_FLIGHT crash recovery), save hooks.
- `e35518d` STAGE_2_UI — opt-in Settings card with explicit consent, status,
  metrics, sync-now, opt-out queue purge.

## Architecture enforced

- Expo → Life backend → standalone SDK → Engine `/api/v1`. No direct Expo→Engine
  path exists; the Engine credential exists only in `.env.server` (gitignored,
  fingerprint-only in status responses).
- SDK wheel certified to contain ONLY `intelligence_maxxxing_client`; installed
  and tested in an empty virtualenv (Core absent, fastapi/sqlalchemy/alembic/
  psycopg absent). Import-linter contracts unchanged: SDK never imports Core,
  Core never imports SDK.
- The Engine gained zero Life-specific logic: `life` is an opaque domain pack;
  registered event types live in LifeMaxxxing's registry.

## Data minimization (certified by canaries against the real ledger)

| Event type | Sent (structured only) | Never sent |
|---|---|---|
| `life.daily_check_in.completed.v1` | happiness, energy, stress, productivity, sleep_hours, calories_consumed/burned, weight, deep_work_blocks, meetings_count, gym_done, football_played, social_activity, alcohol | main_work_win, main_blocker, notes, source |
| `life.workout.completed.v1` | type (controlled vocab), duration_minutes, intensity, bodyweight_kg, exercise_count, total_sets, total_volume_kg | notes, exercises, title, description |

Minimization happens twice: on-device (outbox snapshots are already allow-listed)
and again in the backend registry (single governed boundary).

## Identity

Registered via governed CLI on the real PostgreSQL database:
`application_id=app_079743dd466348c7940d595c736c3557`,
`credential_id=cred_e72dd78a125d7cd796c24441`, scopes exactly
`SUBMIT_OBSERVATION`, `READ_AUDIT`, `READ_INTELLIGENCE`. Secret stored once in
LifeMaxxxing `.env.server`; secret scan gate proves no tracked file contains it.

## Offline & idempotency behaviour

- Engine down: Life backend stays healthy; `/status` reports `reachable=false`;
  sync returns typed retryable 503; records stay in local SQLite and the outbox.
- Outbox: PENDING → IN_FLIGHT → SYNCED / REJECTED / CONFLICT; exponential
  backoff (30s → 1h cap); IN_FLIGHT rows recover to PENDING on app start.
- Idempotency keys are deterministic (`life-<type>-<entity>-<hash>`): the replay
  canary shows the same `observation_id` with `replayed=true`; a conflicting
  payload under the same key is a typed 409 CONFLICT (terminal, no retry).
- Opt-in is explicit (consent dialog); opt-out purges all unsynced queue items.
- No mass backfill: only records saved after opt-in enqueue.

## Test evidence

- Engine suite: **139 passed** (was 132; +7 certification tests), ruff/format/
  mypy/import-linter all green.
- SDK: 9 hermetic unit tests, run twice (repo interpreter + clean venv against
  the installed wheel).
- LifeMaxxxing backend: **48 passed** (was 33; +15), `npx tsc --noEmit` clean,
  ESLint on changed files: 0 errors.
- Cross-repo gate (`run_lifemaxxxing_contract_gates.ps1`): SDK certification,
  fresh Postgres E2E DB, **27 online canaries + 6 offline canaries + secret
  scan — ALL PASSED** (includes cross-application audit isolation: a second
  registered app receives 404 for LifeMaxxxing's audit).

## Explicitly out of scope (unchanged)

Mass backfill of historical Life data, additional event types, Engine-side
domain packs for `life`, inference/intelligence flows back into LifeMaxxxing,
and any other client applications.
