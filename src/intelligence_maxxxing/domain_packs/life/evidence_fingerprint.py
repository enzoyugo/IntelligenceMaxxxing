"""Canonical evidence fingerprint for semantic idempotency (Stage 3.1)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Sequence


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compute_evidence_fingerprint(
    *,
    tenant_id: str,
    owner_id: str,
    application_id: str,
    experiment_id: str,
    protocol_version: str,
    phase: str,
    evidence_cutoff_global_position: int,
    source_event_ids: Sequence[str],
    analysis_method: str,
    analysis_parameters: dict[str, Any],
) -> str:
    unique_sorted = sorted({str(x) for x in source_event_ids})
    material = "\n".join(
        [
            tenant_id,
            owner_id,
            application_id,
            experiment_id,
            protocol_version,
            phase,
            str(evidence_cutoff_global_position),
            ",".join(unique_sorted),
            analysis_method,
            _stable_json(analysis_parameters),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_source_hash(source_event_ids: Iterable[str]) -> str:
    unique_sorted = sorted({str(x) for x in source_event_ids})
    material = "\n".join(unique_sorted)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def source_position_stats(
    positions: Sequence[int],
) -> tuple[int, int | None, int | None]:
    if not positions:
        return 0, None, None
    return len(positions), min(positions), max(positions)
