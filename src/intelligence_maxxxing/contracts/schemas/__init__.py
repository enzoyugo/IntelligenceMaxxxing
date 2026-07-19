"""Canonical schema registry and breaking-change detection support."""

from intelligence_maxxxing.contracts.schemas.registry import (
    PUBLIC_SCHEMAS,
    find_breaking_changes,
    generate_public_schema_snapshot,
)

__all__ = ["PUBLIC_SCHEMAS", "find_breaking_changes", "generate_public_schema_snapshot"]
