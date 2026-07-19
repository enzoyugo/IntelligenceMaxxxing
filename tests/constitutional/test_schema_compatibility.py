"""BREAKING_SCHEMA_CHANGE_DETECTED: public v1 schemas stay compatible.

Committed snapshots live in src/intelligence_maxxxing/contracts/schemas/v1/.
Removing a field, changing its type, or adding a new required field relative
to the snapshot is a breaking change and must go to a new major version.
"""

from intelligence_maxxxing.contracts.schemas import PUBLIC_SCHEMAS, find_breaking_changes


def test_no_breaking_schema_changes() -> None:
    breaking = find_breaking_changes()
    assert not breaking, (
        "Breaking public schema change detected within major version v1:\n"
        + "\n".join(breaking)
        + "\nCreate a new major version instead of breaking existing clients."
    )


def test_all_public_schemas_are_registered() -> None:
    expected = {
        "SubmitObservationRequest",
        "ObservationAcceptedData",
        "AuditRecordData",
        "HealthData",
        "ApiResponseEnvelope",
    }
    assert expected <= set(PUBLIC_SCHEMAS.keys())
