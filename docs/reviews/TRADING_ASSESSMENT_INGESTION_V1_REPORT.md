# Trading Assessment Ingestion V1 Report

**Date:** 2026-07-20

Ingestion validates observation schema semantics (via policy gates), enforces idempotency (`idempotency_key` + payload hash), rejects outcome leakage and future features, persists observation + assessment append-only, returns `im.tmx.assessment.v1`.

Tests: `tests/unit/test_trading_policy_v1.py`, `tests/integration/test_trading_assessment_api.py`.
