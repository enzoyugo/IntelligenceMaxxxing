# IM_AUTH_AND_BOUNDARY_HARDENING_V1_REPORT

## Verdict

`IM_AUTH_BOUNDARY_COMPLETE`

## Changes

- Removed functional default `tmx-im-local-bridge-v1`
- Require `IM_BRIDGE_TOKEN` / `IM_TRADING_BRIDGE_TOKEN`
- `hmac.compare_digest` token check
- `development` alone does not bypass remote writes
- `agents_health` returns 401 when denied (no bare `pass`)
- SDK client default token = `None`

## Tests

`tests/unit/test_bridge_auth_v1.py`
