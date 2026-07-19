"""Health status contract. Health is reported honestly, never assumed."""

from enum import StrEnum

from pydantic import Field

from intelligence_maxxxing.domain.common.base import DomainModel


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"


class ComponentHealth(DomainModel):
    """Health of one component, with an explanation when not healthy."""

    component: str = Field(min_length=1)
    state: HealthState
    detail: str | None = None


class HealthStatus(DomainModel):
    """Aggregated Engine health."""

    status: HealthState
    components: tuple[ComponentHealth, ...] = ()

    @staticmethod
    def aggregate(components: tuple[ComponentHealth, ...]) -> "HealthStatus":
        """Overall state is the worst component state. Degradation is never hidden."""
        if any(c.state is HealthState.UNHEALTHY for c in components):
            overall = HealthState.UNHEALTHY
        elif any(c.state is HealthState.DEGRADED for c in components):
            overall = HealthState.DEGRADED
        else:
            overall = HealthState.HEALTHY
        return HealthStatus(status=overall, components=components)
