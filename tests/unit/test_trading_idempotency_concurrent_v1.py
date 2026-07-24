"""P1-D: concurrent same-key assessments yield one assessment_id."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from intelligence_maxxxing.application.errors import IdempotencyConflictError
from intelligence_maxxxing.application.use_cases.trading_assessment import TradingAssessmentService
from intelligence_maxxxing.infrastructure.trading.jsonl_store import TradingJsonlStore
from intelligence_maxxxing.infrastructure.trading.sqlite_idempotency_store import (
    TradingSqliteIdempotencyStore,
)


def _obs(key: str, *, n: int = 1) -> dict:
    return {
        "idempotency_key": key,
        "observation_id": f"OBS_{key}_{n}",
        "experiment_id": "EXP_test",
        "economic_setup": {"economic_setup_id": "ES_concurrent_test_001"},
        "payload_marker": n,
    }


def test_same_key_same_payload_concurrent_returns_one_assessment(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = TradingJsonlStore(root=root)
    idem = TradingSqliteIdempotencyStore(path=root / "idem.sqlite3")
    svc = TradingAssessmentService(store=store, idem_store=idem)
    key = "idem_concurrent_same"
    base = _obs(key, n=1)
    # Identical payload hash: same observation body for all workers.
    body = {**base, "observation_id": "OBS_shared"}

    def _call():
        return svc.assess(dict(body), request_id="req_c")

    ids: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(_call) for _ in range(8)]
        for f in as_completed(futs):
            ids.append(f.result()["assessment_id"])
    assert len(set(ids)) == 1
    assert store.counts()["assessments"] == 1


def test_same_key_same_payload_returns_same_assessment_id(tmp_path: Path) -> None:
    root = tmp_path / "store2"
    svc = TradingAssessmentService(
        store=TradingJsonlStore(root=root),
        idem_store=TradingSqliteIdempotencyStore(path=root / "idem.sqlite3"),
    )
    body = _obs("idem_serial", n=1)
    a = svc.assess(body)
    b = svc.assess(body)
    assert a["assessment_id"] == b["assessment_id"]


def test_same_key_different_payload_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "store3"
    svc = TradingAssessmentService(
        store=TradingJsonlStore(root=root),
        idem_store=TradingSqliteIdempotencyStore(path=root / "idem.sqlite3"),
    )
    key = "idem_conflict"
    svc.assess(_obs(key, n=1))
    try:
        svc.assess(_obs(key, n=2))
        raised = False
    except IdempotencyConflictError:
        raised = True
    assert raised is True
