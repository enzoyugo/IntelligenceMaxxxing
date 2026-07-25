"""Deterministic pure-Python model suite (no LLM, optional sklearn-free)."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from typing import Any


FEATURE_KEYS = (
    "hour_utc",
    "dow_utc",
    "session_code",
    "symbol_code",
    "strategy_code",
    "direction_code",
)


def _vec(row: dict[str, Any]) -> list[float]:
    feats = row.get("features") or {}
    return [float(feats.get(k) or 0.0) for k in FEATURE_KEYS]


class RidgeExpectancyModelV1:
    """Closed-form ridge regression y ~ features (train-fold only)."""

    def __init__(self, lam: float = 1.0) -> None:
        self.lam = lam
        self.coef: list[float] = []
        self.intercept: float = 0.0
        self.n: int = 0
        self.feature_means: list[float] = []
        self.feature_stds: list[float] = []

    def fit(self, rows: list[dict[str, Any]]) -> None:
        xs: list[list[float]] = []
        ys: list[float] = []
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
            xs.append(_vec(row))
            ys.append(yf)
        self.n = len(ys)
        if self.n == 0:
            self.coef = [0.0] * len(FEATURE_KEYS)
            self.intercept = 0.0
            self.feature_means = [0.0] * len(FEATURE_KEYS)
            self.feature_stds = [1.0] * len(FEATURE_KEYS)
            return
        d = len(FEATURE_KEYS)
        means = [sum(x[j] for x in xs) / self.n for j in range(d)]
        stds = []
        for j in range(d):
            var = sum((x[j] - means[j]) ** 2 for x in xs) / max(1, self.n - 1)
            stds.append(math.sqrt(var) if var > 1e-12 else 1.0)
        self.feature_means = means
        self.feature_stds = stds
        # Center y; solve (X'X + lam I) b = X'y with standardized X
        xtx = [[0.0] * d for _ in range(d)]
        xty = [0.0] * d
        y_mean = sum(ys) / self.n
        for x, y in zip(xs, ys):
            xn = [(x[j] - means[j]) / stds[j] for j in range(d)]
            yr = y - y_mean
            for i in range(d):
                xty[i] += xn[i] * yr
                for j in range(d):
                    xtx[i][j] += xn[i] * xn[j]
        for i in range(d):
            xtx[i][i] += self.lam
        self.coef = _solve(xtx, xty)
        self.intercept = y_mean

    def predict(self, row: dict[str, Any]) -> float:
        x = _vec(row)
        s = self.intercept
        for j, c in enumerate(self.coef):
            s += c * ((x[j] - self.feature_means[j]) / self.feature_stds[j])
        return float(s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "ridge_expectancy_v1",
            "lam": self.lam,
            "n": self.n,
            "coef": self.coef,
            "intercept": self.intercept,
            "feature_keys": list(FEATURE_KEYS),
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
        }

    def artifact_hash(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")
        ).hexdigest()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RidgeExpectancyModelV1":
        m = cls(lam=float(raw.get("lam") or 1.0))
        m.n = int(raw.get("n") or 0)
        m.coef = list(raw.get("coef") or [])
        m.intercept = float(raw.get("intercept") or 0.0)
        m.feature_means = list(raw.get("feature_means") or [0.0] * len(FEATURE_KEYS))
        m.feature_stds = list(raw.get("feature_stds") or [1.0] * len(FEATURE_KEYS))
        return m


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            continue
        m[col], m[piv] = m[piv], m[col]
        div = m[col][col]
        for j in range(col, n + 1):
            m[col][j] /= div
        for r in range(n):
            if r == col:
                continue
            factor = m[r][col]
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]
    return [m[i][n] for i in range(n)]


class BucketClassifierV1:
    """Discrete TAKE/SKIP prior from train expectancy buckets (diagnostic)."""

    def __init__(self) -> None:
        self.bucket_mean: dict[str, float] = {}
        self.bucket_n: dict[str, int] = {}

    def fit(self, rows: list[dict[str, Any]]) -> None:
        bags: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            y = row.get("label_trusted_net_R")
            if y is None:
                continue
            feats = row.get("features") or {}
            key = f"{row.get('strategy_id')}|{feats.get('session_bucket')}|{feats.get('hour_bucket')}"
            bags[key].append(float(y))
        self.bucket_mean = {k: sum(v) / len(v) for k, v in bags.items() if v}
        self.bucket_n = {k: len(v) for k, v in bags.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": "bucket_classifier_v1",
            "bucket_mean": self.bucket_mean,
            "bucket_n": self.bucket_n,
        }
