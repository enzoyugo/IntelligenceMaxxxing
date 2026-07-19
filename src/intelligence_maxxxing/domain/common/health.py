"""Health status contracts. Health is measured, never assumed.

Stage 1 adds HealthSnapshot: a timestamped record of which components were
actually checked and what was observed. Audits embed real snapshots; nothing
may be marked HEALTHY without having been measured.
"""

from enum import StrEnum

from pydantic import Field

from intelligence_maxxxing.domain.common.base import DomainModel, UtcDatetime


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"
    NOT_CHECKED = "NOT_CHECKED"


class ComponentHealth(DomainModel):
    """Health of one component, with an explanation when not healthy."""

    component: str = Field(min_length=1)
    state: HealthState
    detail: str | None = None


class HealthComponentStatus(DomainModel):
    """A component's status inside a snapshot, with measurement provenance."""

    component: str = Field(min_length=1)
    state: HealthState
    checked: bool = Field(description="True only when the state was actually measured")
    detail: str | None = None


class HealthSnapshot(DomainModel):
    """What was measured, what was not, and when.

    A component may only appear with checked=True if it was really probed.
    Unchecked components must carry state NOT_CHECKED.
    """

    snapshot_id: str = Field(min_length=1)
    checked_at: UtcDatetime
    components: tuple[HealthComponentStatus, ...] = ()

    def checked_components(self) -> tuple[HealthComponentStatus, ...]:
        return tuple(c for c in self.components if c.checked)

    def unchecked_components(self) -> tuple[HealthComponentStatus, ...]:
        return tuple(c for c in self.components if not c.checked)


class HealthStatus(DomainModel):
    """Aggregated Engine health over the *checked* components."""

    status: HealthState
    components: tuple[ComponentHealth, ...] = ()

    @staticmethod
    def aggregate(components: tuple[ComponentHealth, ...]) -> "HealthStatus":
        """Overall state is the worst measured state. Degradation is never hidden."""
        measured = [c for c in components if c.state is not HealthState.NOT_CHECKED]
        if any(c.state is HealthState.UNHEALTHY for c in measured):
            overall = HealthState.UNHEALTHY
        elif any(c.state in (HealthState.DEGRADED, HealthState.UNKNOWN) for c in measured):
            overall = HealthState.DEGRADED
        elif measured:
            overall = HealthState.HEALTHY
        else:
            overall = HealthState.UNKNOWN
        return HealthStatus(status=overall, components=components)
