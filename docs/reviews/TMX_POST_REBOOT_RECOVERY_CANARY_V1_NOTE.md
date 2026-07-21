# TMX Post-Reboot Recovery Canary V1 — IM note

**Date:** 2026-07-21  
**IM tip at verification:** descendant of connectivity note `bfa167a`  
**Owner:** TradingMaxxxing connectivity watchdog / canaries

IM Engine `:8100` was fault-injected and recovered by TMX watchdog (research-only process restart).  
**Policy `IM_TRADING_DECISION_POLICY@1.0.0` and Agent Bundle were not modified.**

TMX executive verdict: `RECOVERY_CANARIES_PASS_REBOOT_UNTESTED`  
(Autostart via HKCU Run AtLogon; AtStartup Scheduled Task still needs Administrator.)

See TMX: `docs/reviews/POST_REBOOT_AUTOSTART_AND_RECOVERY_CANARY_V1_MASTER_REPORT.md`.
