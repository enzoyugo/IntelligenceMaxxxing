"""Health snapshot honesty.

AUDIT_USES_MEASURED_HEALTH_SNAPSHOT / UNCHECKED_COMPONENT_NOT_MARKED_HEALTHY
"""

from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.health import (
    ComponentHealth,
    HealthComponentStatus,
    HealthSnapshot,
    HealthState,
    HealthStatus,
)


def test_unchecked_component_not_marked_healthy() -> None:
    snapshot = HealthSnapshot(
        snapshot_id="hsnap_x",
        checked_at=utc_now(),
        components=(
            HealthComponentStatus(component="api", state=HealthState.HEALTHY, checked=True),
            HealthComponentStatus(
                component="vector_index", state=HealthState.NOT_CHECKED, checked=False
            ),
        ),
    )
    unchecked = snapshot.unchecked_components()
    assert len(unchecked) == 1
    assert unchecked[0].state is HealthState.NOT_CHECKED
    assert unchecked[0].checked is False
    status = HealthStatus.aggregate(
        tuple(ComponentHealth(component=c.component, state=c.state) for c in snapshot.components)
    )
    assert status.status is HealthState.HEALTHY


def test_audit_uses_measured_health_snapshot(client: object) -> None:
    """Submitting an observation persists a real HealthSnapshot, not a literal."""
    import uuid

    from fastapi.testclient import TestClient

    from tests.conftest import valid_observation_payload

    assert isinstance(client, TestClient)
    response = client.post(
        "/api/v1/observations",
        json=valid_observation_payload(),
        headers={"Idempotency-Key": f"hsnap-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 201
    audit_id = response.json()["data"]["audit_id"]
    audit = client.get(f"/api/v1/audits/{audit_id}").json()["data"]
    health_state = audit["health_state"]
    assert "snapshot_id" in health_state
    assert "checked_at" in health_state
    assert "components" in health_state
    components = {c["component"]: c for c in health_state["components"]}
    assert components["database"]["checked"] is True
    # Nothing unchecked may appear as HEALTHY.
    for component in health_state["components"]:
        if not component["checked"]:
            assert component["state"] == "NOT_CHECKED"
