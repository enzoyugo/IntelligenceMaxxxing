"""Real database health check. Reports degradation honestly."""

from sqlalchemy import Engine, text

from intelligence_maxxxing.application.ports import DatabaseHealthPort
from intelligence_maxxxing.domain.common.health import ComponentHealth, HealthState


class SqlAlchemyDatabaseHealth(DatabaseHealthPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> ComponentHealth:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:
            return ComponentHealth(
                component="database",
                state=HealthState.UNHEALTHY,
                detail=f"{type(exc).__name__}: connection failed",
            )
        return ComponentHealth(component="database", state=HealthState.HEALTHY)
