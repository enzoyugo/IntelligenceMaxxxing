"""Transactional trading idempotency (SQLite WAL) — coordination source of truth.

JSONL remains an append-only audit mirror, not the concurrent claim primitive.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


def default_sqlite_path() -> Path:
    override = os.environ.get("IM_TRADING_IDEMPOTENCY_DB")
    if override:
        return Path(override)
    root = os.environ.get("IM_TRADING_STORE_DIR")
    if root:
        return Path(root) / "trading_idempotency_v1.sqlite3"
    return Path(__file__).resolve().parents[4] / "data" / "trading_bridge_v1" / "trading_idempotency_v1.sqlite3"


class TradingSqliteIdempotencyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_sqlite_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init(self) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_idempotency (
                  idempotency_key TEXT PRIMARY KEY,
                  request_hash TEXT NOT NULL,
                  observation_id TEXT,
                  assessment_id TEXT,
                  policy_version TEXT,
                  bundle_version TEXT,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  completed_at TEXT,
                  response_payload_json TEXT,
                  response_payload_hash TEXT
                )
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_trading_assessment_id "
                "ON trading_idempotency(assessment_id) WHERE assessment_id IS NOT NULL"
            )
        finally:
            conn.close()

    def claim_or_get(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        created_at: str,
    ) -> dict[str, Any]:
        """BEGIN IMMEDIATE claim. Returns existing complete, conflict, or pending claim."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM trading_idempotency WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row:
                if str(row["request_hash"]) != request_hash:
                    conn.execute("COMMIT")
                    return {"status": "CONFLICT", "row": dict(row)}
                if str(row["status"]) == "COMPLETE" and row["response_payload_json"]:
                    conn.execute("COMMIT")
                    return {
                        "status": "COMPLETE",
                        "row": dict(row),
                        "response": json.loads(row["response_payload_json"]),
                    }
                # Pending: wait briefly for peer; do not create a second assessment.
                conn.execute("COMMIT")
                return {"status": "PENDING", "row": dict(row)}
            conn.execute(
                """
                INSERT INTO trading_idempotency(
                  idempotency_key, request_hash, status, created_at
                ) VALUES (?,?,?,?)
                """,
                (idempotency_key, request_hash, "PENDING", created_at),
            )
            conn.execute("COMMIT")
            return {"status": "CLAIMED", "row": {"idempotency_key": idempotency_key, "request_hash": request_hash}}
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            # Lost race on insert — re-read winner.
            row = conn.execute(
                "SELECT * FROM trading_idempotency WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row and str(row["request_hash"]) != request_hash:
                return {"status": "CONFLICT", "row": dict(row) if row else {}}
            if row and str(row["status"]) == "COMPLETE" and row["response_payload_json"]:
                return {
                    "status": "COMPLETE",
                    "row": dict(row),
                    "response": json.loads(row["response_payload_json"]),
                }
            return {"status": "PENDING", "row": dict(row) if row else {}}
        finally:
            conn.close()

    def wait_complete(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        timeout_s: float = 2.0,
        poll_s: float = 0.05,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT * FROM trading_idempotency WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
            finally:
                conn.close()
            if not row:
                return None
            if str(row["request_hash"]) != request_hash:
                return {"status": "CONFLICT", "row": dict(row)}
            if str(row["status"]) == "COMPLETE" and row["response_payload_json"]:
                return {
                    "status": "COMPLETE",
                    "row": dict(row),
                    "response": json.loads(row["response_payload_json"]),
                }
            time.sleep(poll_s)
        return {"status": "PENDING_TIMEOUT", "row": {"idempotency_key": idempotency_key}}

    def complete(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        observation_id: str | None,
        assessment_id: str,
        policy_version: str | None,
        response: dict[str, Any],
        response_hash: str,
        completed_at: str,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE trading_idempotency SET
                  status='COMPLETE',
                  observation_id=?,
                  assessment_id=?,
                  policy_version=?,
                  completed_at=?,
                  response_payload_json=?,
                  response_payload_hash=?
                WHERE idempotency_key=? AND request_hash=? AND status='PENDING'
                """,
                (
                    observation_id,
                    assessment_id,
                    policy_version,
                    completed_at,
                    json.dumps(response, separators=(",", ":"), ensure_ascii=True),
                    response_hash,
                    idempotency_key,
                    request_hash,
                ),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()

    def mark_failed(self, *, idempotency_key: str, request_hash: str) -> None:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE trading_idempotency SET status='FAILED' "
                "WHERE idempotency_key=? AND request_hash=? AND status='PENDING'",
                (idempotency_key, request_hash),
            )
            conn.execute("COMMIT")
        finally:
            conn.close()
