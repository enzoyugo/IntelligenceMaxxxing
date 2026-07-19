"""Deterministic event hashing for the integrity chain.

The chain is maintained PER (owner_id, application_id) STREAM (not globally),
so unrelated applications never contend on one global head.

This is tamper/corruption DETECTION, not absolute cryptographic security:
an attacker with full database write access and knowledge of the scheme could
rewrite a whole chain. The goal is to make silent alteration detectable.
"""

import hashlib
import json

from intelligence_maxxxing.domain.audit.models import EngineEvent

# Canonical fields included in the hash material, in fixed order.
_HASH_FIELDS = (
    "event_id",
    "event_type",
    "schema_version",
    "aggregate_type",
    "aggregate_id",
    "aggregate_version",
    "domain_pack",
    "tenant_id",
    "owner_id",
    "application_id",
    "occurred_at",
    "recorded_at",
    "audit_id",
    "request_id",
    "payload",
)


def compute_event_hash(event: EngineEvent, previous_event_hash: str | None) -> str:
    """SHA-256 over a deterministic serialization of canonical event fields.

    The previous hash of the same (owner, application) stream is chained in,
    so altering or removing any past event breaks every later hash.
    """
    dumped = event.model_dump(mode="json", include=set(_HASH_FIELDS))
    material = {field: dumped[field] for field in _HASH_FIELDS}
    material["previous_event_hash"] = previous_event_hash
    material["actor_type"] = event.actor.actor_type.value
    material["actor_id"] = event.actor.actor_id
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(
    events: list[EngineEvent],
    initial_previous_hash: str | None = None,
) -> tuple[bool, str | None]:
    """Verify one stream's chain (events in ascending global order).

    Returns (ok, first_broken_event_id).

    `initial_previous_hash` is the anchor that the FIRST event in ``events``
    must chain onto. For a FULL verification of a whole stream it is None
    (the chain has no predecessor). For an INCREMENTAL verification that starts
    in the middle of a stream, it is the ``last_verified_hash`` of the trusted
    checkpoint the range begins after; a legitimate anchor is NEVER mistaken
    for corruption.

    Legacy events with no hash are tolerated only at the very start of a
    stream, before the chain began (and only when there is no anchor).
    """
    previous_hash: str | None = initial_previous_hash
    chain_started = initial_previous_hash is not None
    for event in events:
        if event.event_hash is None:
            if chain_started:
                return False, event.event_id
            continue
        expected = compute_event_hash(event, event.previous_event_hash)
        if event.event_hash != expected or event.previous_event_hash != previous_hash:
            return False, event.event_id
        previous_hash = event.event_hash
        chain_started = True
    return True, None
