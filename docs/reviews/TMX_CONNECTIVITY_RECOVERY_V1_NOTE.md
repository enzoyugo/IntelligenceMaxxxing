# TMX Connectivity Recovery V1 — IM note

**Date:** 2026-07-21  
**IM baseline:** `364651c`  
**Owner:** TradingMaxxxing (`connectivity_recovery_v1`)

IM is **not** the recovery controller. TMX ConnectivityHealthV1 probes IM `:8100` trading health as a dependency signal and may restart the IM Engine process if it is down — research-only, no trading mutation, no Policy `IM_TRADING_DECISION_POLICY@1.0.0` or Agent Bundle changes.

**TMX verdict:** `MULTI_CAUSE_OPERATIONAL_STALL` with `INTERNET_OUTAGE_NOT_CONFIRMED` and `HOST_SLEEP_OR_RESTART_CONFIRMED` (host reboot 2026-07-21 ~18:45 local).

See TMX report: `docs/reviews/CONNECTIVITY_ROOT_CAUSE_AND_SELF_RECOVERY_V1_MASTER_REPORT.md`.
