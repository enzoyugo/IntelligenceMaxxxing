"""IM meta-edge research pack tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelligence_maxxxing.domain_packs.trading.meta_edge_v1 import (
    LIVE_POLICY_INFLUENCE,
    PROMOTION_ELIGIBLE,
    RESEARCH_POLICY_ID,
)
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.base_rate_store import BaseRateStoreV1
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.contracts import (
    validate_observation,
    validate_training_row,
)
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.inference import (
    infer_from_observations,
    train_from_inbox,
)
from intelligence_maxxxing.domain_packs.trading.meta_edge_v1.selective_policy import (
    assess_observation,
)


def test_research_policy_not_promotable():
    assert PROMOTION_ELIGIBLE is False
    assert LIVE_POLICY_INFLUENCE is False
    assert RESEARCH_POLICY_ID.startswith("IM_TRADING_META_EDGE")


def test_no_tmx_import_in_pack():
    root = Path(__file__).resolve().parents[4] / "src" / "intelligence_maxxxing" / "domain_packs" / "trading" / "meta_edge_v1"
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("import ") or s.startswith("from "):
                assert "tradingmaxxing" not in s


def test_observation_rejects_outcomes_and_oos():
    bad = {
        "contract": "tmx.im.meta_edge_observation.v1",
        "origin": "TEST_OOS",
        "trusted_net_R": 1.0,
    }
    errs = validate_observation(bad)
    assert any("OUTCOME" in e or "FORBIDDEN" in e for e in errs)


def test_training_origin_rules():
    ok = {
        "contract": "tmx.im.meta_edge_training_row.v1",
        "origin": "TRAIN",
        "label_trusted_net_R": 0.1,
    }
    assert validate_training_row(ok) == []
    bad = {**ok, "origin": "FORWARD"}
    assert validate_training_row(bad)


def test_base_rate_and_assess(tmp_path: Path):
    rows = []
    for i in range(40):
        rows.append(
            {
                "contract": "tmx.im.meta_edge_training_row.v1",
                "origin": "TRAIN",
                "economic_setup_id": f"e{i}",
                "strategy_id": "S1",
                "symbol": "EURUSD",
                "features": {"session_bucket": "NY", "hour_bucket": "H12_16", "hour_utc": 12},
                "label_trusted_net_R": 0.2,
            }
        )
    train_path = tmp_path / "train.jsonl"
    train_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    art = tmp_path / "art"
    receipt = train_from_inbox(
        inbox_training_jsonl=train_path,
        artifact_dir=art,
        split_hash="split",
        feature_registry_hash="feat",
    )
    assert receipt["n_train_rows"] == 40
    obs = {
        "contract": "tmx.im.meta_edge_observation.v1",
        "origin": "VALIDATION_EVAL",
        "economic_setup_id": "x1",
        "strategy_id": "S1",
        "symbol": "EURUSD",
        "features": {"session_bucket": "NY", "hour_bucket": "H12_16"},
        "feature_registry_hash": "feat",
        "split_hash": "split",
    }
    store = BaseRateStoreV1.load(art / "base_rate_store.json")
    a = assess_observation(obs, store, feature_registry_hash="feat", split_hash="split")
    assert a["decision"] == "TAKE"
    obs_path = tmp_path / "obs.jsonl"
    obs_path.write_text(json.dumps(obs) + "\n", encoding="utf-8")
    summary = infer_from_observations(
        observations_jsonl=obs_path,
        artifact_dir=art,
        out_assessments_jsonl=tmp_path / "out.jsonl",
    )
    assert summary["n_assessments"] == 1


def test_frozen_policy_file_unchanged_bytes_marker():
    # Sanity: research pack must not live inside policy_v1.py mutation path.
    policy = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "intelligence_maxxxing"
        / "domain_packs"
        / "trading"
        / "policy_v1.py"
    )
    text = policy.read_text(encoding="utf-8")
    assert "IM_TRADING_DECISION_POLICY@1.0.0" in text or "1.0.0" in text
    assert "META_EDGE_RESEARCH_POLICY" not in text
