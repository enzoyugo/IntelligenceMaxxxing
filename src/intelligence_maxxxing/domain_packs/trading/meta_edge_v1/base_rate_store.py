"""Hierarchical base-rate store learned only from allowed training folds."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIN_N_LEAF = 30
MIN_N_PARENT = 80


@dataclass(frozen=True)
class BaseRateKey:
    strategy_id: str
    symbol: str
    session_bucket: str
    hour_bucket: str


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


class BaseRateStoreV1:
    """Hierarchy: strategy|symbol|session|hour → strategy|symbol|session → strategy|symbol → strategy → global."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self.n_rows = 0
        self.split_hash: str | None = None

    def _key(self, *parts: str) -> str:
        return "|".join(parts)

    def fit(self, rows: list[dict[str, Any]], *, split_hash: str) -> None:
        self._buckets.clear()
        self.n_rows = 0
        self.split_hash = split_hash
        for row in rows:
            y = row.get("label_trusted_net_R")
            if y is None:
                continue
            try:
                yf = float(y)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(yf):
                continue
            feats = row.get("features") or {}
            sid = str(row.get("strategy_id") or "UNK")
            sym = str(row.get("symbol") or "UNK")
            sess = str(feats.get("session_bucket") or "UNK")
            hour = str(feats.get("hour_bucket") or "UNK")
            for key in (
                self._key("L4", sid, sym, sess, hour),
                self._key("L3", sid, sym, sess),
                self._key("L2", sid, sym),
                self._key("L1", sid),
                self._key("L0", "GLOBAL"),
            ):
                self._buckets[key].append(yf)
            self.n_rows += 1

    def lookup(self, row: dict[str, Any]) -> dict[str, Any]:
        feats = row.get("features") or {}
        sid = str(row.get("strategy_id") or "UNK")
        sym = str(row.get("symbol") or "UNK")
        sess = str(feats.get("session_bucket") or "UNK")
        hour = str(feats.get("hour_bucket") or "UNK")
        candidates = [
            (self._key("L4", sid, sym, sess, hour), MIN_N_LEAF, "strategy_symbol_session_hour"),
            (self._key("L3", sid, sym, sess), MIN_N_LEAF, "strategy_symbol_session"),
            (self._key("L2", sid, sym), MIN_N_PARENT, "strategy_symbol"),
            (self._key("L1", sid), MIN_N_PARENT, "strategy"),
            (self._key("L0", "GLOBAL"), 1, "global"),
        ]
        for key, min_n, level in candidates:
            xs = self._buckets.get(key) or []
            if len(xs) >= min_n:
                return {
                    "expected_net_R": _mean(xs),
                    "n": len(xs),
                    "level": level,
                    "key": key,
                    "sufficient": True,
                }
        return {
            "expected_net_R": None,
            "n": 0,
            "level": "insufficient",
            "key": None,
            "sufficient": False,
        }

    def to_dict(self) -> dict[str, Any]:
        summary = {
            k: {"n": len(v), "mean": _mean(v)} for k, v in sorted(self._buckets.items()) if v
        }
        return {
            "version": "meta_edge_base_rate_store_v1",
            "split_hash": self.split_hash,
            "n_rows": self.n_rows,
            "buckets": summary,
        }

    def artifact_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def save(self, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.artifact_hash()

    @classmethod
    def load(cls, path: Path) -> "BaseRateStoreV1":
        raw = json.loads(path.read_text(encoding="utf-8"))
        store = cls()
        store.split_hash = raw.get("split_hash")
        store.n_rows = int(raw.get("n_rows") or 0)
        for key, meta in (raw.get("buckets") or {}).items():
            mean = meta.get("mean")
            n = int(meta.get("n") or 0)
            if mean is None or n <= 0:
                continue
            # Reconstruct approximate bag as n copies of mean (sufficient for lookup means).
            store._buckets[key] = [float(mean)] * n
        return store
