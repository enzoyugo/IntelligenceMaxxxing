"""Registry of public schemas and structural breaking-change detection.

A snapshot of the public JSON Schemas is committed under
contracts/schemas/v1/. Removing a field, adding a new required field, or
changing a field's type relative to the snapshot is a breaking change and must
fail constitutional tests until a new major version is created.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from intelligence_maxxxing.contracts.api.audits import AuditRecordData
from intelligence_maxxxing.contracts.api.envelope import ApiResponseEnvelope
from intelligence_maxxxing.contracts.api.health import HealthData
from intelligence_maxxxing.contracts.api.observations import (
    ObservationAcceptedData,
    ObservationListData,
    ObservationView,
    SubmitObservationRequest,
)

PUBLIC_SCHEMAS: dict[str, type[BaseModel]] = {
    "SubmitObservationRequest": SubmitObservationRequest,
    "ObservationAcceptedData": ObservationAcceptedData,
    "ObservationView": ObservationView,
    "ObservationListData": ObservationListData,
    "AuditRecordData": AuditRecordData,
    "HealthData": HealthData,
    "ApiResponseEnvelope": ApiResponseEnvelope,
}

SNAPSHOT_DIR = Path(__file__).parent / "v1"


def generate_public_schema_snapshot() -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema() for name, model in PUBLIC_SCHEMAS.items()}


def _properties(schema: dict[str, Any]) -> dict[str, Any]:
    props: dict[str, Any] = schema.get("properties", {})
    return props


def _compare_object(
    name: str, old: dict[str, Any], new: dict[str, Any], breaking: list[str]
) -> None:
    old_props = _properties(old)
    new_props = _properties(new)
    old_required = set(old.get("required", []))
    new_required = set(new.get("required", []))

    for field in old_props:
        if field not in new_props:
            breaking.append(f"{name}: field '{field}' was removed")
    for field in new_required - old_required:
        if field not in old_props:
            breaking.append(f"{name}: new required field '{field}' was added")
    for field, old_def in old_props.items():
        new_def = new_props.get(field)
        if new_def is None:
            continue
        old_type = old_def.get("type") or old_def.get("$ref") or old_def.get("anyOf")
        new_type = new_def.get("type") or new_def.get("$ref") or new_def.get("anyOf")
        if old_type != new_type:
            breaking.append(f"{name}: field '{field}' changed type")


def find_breaking_changes(snapshot_dir: Path = SNAPSHOT_DIR) -> list[str]:
    """Compare committed v1 snapshots against current models. Empty list = compatible."""
    breaking: list[str] = []
    current = generate_public_schema_snapshot()
    for name in PUBLIC_SCHEMAS:
        snapshot_path = snapshot_dir / f"{name}.json"
        if not snapshot_path.is_file():
            breaking.append(f"{name}: missing committed schema snapshot")
            continue
        old = json.loads(snapshot_path.read_text(encoding="utf-8"))
        new = current[name]
        _compare_object(name, old, new, breaking)
        old_defs = old.get("$defs", {})
        new_defs = new.get("$defs", {})
        for def_name, old_def in old_defs.items():
            if def_name not in new_defs:
                breaking.append(f"{name}.$defs: definition '{def_name}' was removed")
            elif old_def.get("properties"):
                _compare_object(f"{name}.{def_name}", old_def, new_defs[def_name], breaking)
    return breaking
