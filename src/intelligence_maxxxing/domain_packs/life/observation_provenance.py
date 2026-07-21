"""Typed observation purpose / environment for wellbeing isolation.

Constitution-compatible: values travel in existing Context.environment and
metadata (LimitedMetadata). Closed enums — no arbitrary strings.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ObservationEnvironment(StrEnum):
    PRODUCTION = "PRODUCTION"
    TEST = "TEST"
    DEVELOPMENT = "DEVELOPMENT"


class ObservationPurpose(StrEnum):
    USER_OBSERVATION = "USER_OBSERVATION"
    SMOKE_TEST = "SMOKE_TEST"
    CONTRACT_TEST = "CONTRACT_TEST"
    FIXTURE = "FIXTURE"
    MIGRATION = "MIGRATION"
    BACKFILL = "BACKFILL"
    DEMO = "DEMO"


class SubjectScope(StrEnum):
    PERSONAL = "PERSONAL"
    TEST_PROFILE = "TEST_PROFILE"
    SHARED_DEMO = "SHARED_DEMO"


# Non-productive purposes never enter personal wellbeing scores.
NON_PRODUCTIVE_PURPOSES = frozenset(
    {
        ObservationPurpose.SMOKE_TEST,
        ObservationPurpose.CONTRACT_TEST,
        ObservationPurpose.FIXTURE,
        ObservationPurpose.DEMO,
    }
)


def parse_environment(raw: Any) -> ObservationEnvironment | None:
    if raw is None:
        return None
    text = str(raw).strip().upper()
    aliases = {
        "PRODUCTION": ObservationEnvironment.PRODUCTION,
        "PROD": ObservationEnvironment.PRODUCTION,
        "TEST": ObservationEnvironment.TEST,
        "DEVELOPMENT": ObservationEnvironment.DEVELOPMENT,
        "DEV": ObservationEnvironment.DEVELOPMENT,
    }
    return aliases.get(text)


def parse_purpose(raw: Any) -> ObservationPurpose | None:
    if raw is None:
        return None
    text = str(raw).strip().upper()
    try:
        return ObservationPurpose(text)
    except ValueError:
        return None


def parse_subject_scope(raw: Any) -> SubjectScope | None:
    if raw is None:
        return None
    text = str(raw).strip().upper()
    try:
        return SubjectScope(text)
    except ValueError:
        return None


def extract_provenance(row: Any) -> dict[str, Any]:
    """Pull purpose/environment/scope from a projected observation-like object."""
    ctx = getattr(row, "context", None)
    if not isinstance(ctx, dict):
        ctx = {}
    meta = getattr(row, "metadata", None)
    if not isinstance(meta, dict):
        meta = {}
    attrs = ctx.get("attributes") if isinstance(ctx.get("attributes"), dict) else {}
    return {
        "environment": parse_environment(ctx.get("environment") or meta.get("environment")),
        "purpose": parse_purpose(
            meta.get("observation_purpose")
            or attrs.get("observation_purpose")
            or meta.get("purpose")
        ),
        "subject_scope": parse_subject_scope(
            meta.get("subject_scope") or attrs.get("subject_scope")
        ),
        "test_run_id": meta.get("test_run_id") or attrs.get("test_run_id"),
        "source_ids": list(getattr(row, "source_ids", None) or []),
        "observation_id": getattr(row, "observation_id", None),
        "metadata": meta,
        "context": ctx,
    }
