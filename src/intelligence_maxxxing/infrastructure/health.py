"""Database health probe and measured HealthSnapshotProvider (Stage 1 §15).

Audits obtain their health_state exclusively from HealthSnapshotProvider.
Nothing is marked HEALTHY unless it was actually measured.
"""

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from intelligence_maxxxing.application.ports import (
    DatabaseHealthPort,
    HealthSnapshotProviderPort,
)
from intelligence_maxxxing.domain.common.base import utc_now
from intelligence_maxxxing.domain.common.health import (
    ComponentHealth,
    HealthComponentStatus,
    HealthSnapshot,
    HealthState,
)
from intelligence_maxxxing.domain.common.identifiers import SNAPSHOT_PREFIX, new_id
from intelligence_maxxxing.governance.manifest import find_constitutional_dir, verify_manifest


class SqlAlchemyDatabaseHealth(DatabaseHealthPort):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def check(self) -> ComponentHealth:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return ComponentHealth(component="database", state=HealthState.HEALTHY)
        except SQLAlchemyError as exc:
            return ComponentHealth(
                component="database",
                state=HealthState.UNHEALTHY,
                detail=f"database unreachable: {type(exc).__name__}",
            )


class MeasuredHealthSnapshotProvider(HealthSnapshotProviderPort):
    """Captures a real snapshot of the components that can be measured now.

    Components that are not probed in this capture are recorded as
    NOT_CHECKED with checked=False. Audits never invent HEALTHY.
    """

    def __init__(
        self,
        database_health: DatabaseHealthPort,
        *,
        check_manifest: bool = True,
        check_api: bool = True,
    ) -> None:
        self._database_health = database_health
        self._check_manifest = check_manifest
        self._check_api = check_api

    def capture(self) -> HealthSnapshot:
        components: list[HealthComponentStatus] = []

        if self._check_api:
            # The API process is alive if this code is running.
            components.append(
                HealthComponentStatus(component="api", state=HealthState.HEALTHY, checked=True)
            )
        else:
            components.append(
                HealthComponentStatus(component="api", state=HealthState.NOT_CHECKED, checked=False)
            )

        db = self._database_health.check()
        components.append(
            HealthComponentStatus(
                component="database",
                state=db.state,
                checked=True,
                detail=db.detail,
            )
        )

        if self._check_manifest:
            try:
                from pathlib import Path

                result = verify_manifest(find_constitutional_dir(Path.cwd()))
                components.append(
                    HealthComponentStatus(
                        component="constitution_manifest",
                        state=(HealthState.HEALTHY if result.ok else HealthState.UNHEALTHY),
                        checked=True,
                        detail=None if result.ok else "constitutional manifest mismatch",
                    )
                )
            except Exception as exc:
                components.append(
                    HealthComponentStatus(
                        component="constitution_manifest",
                        state=HealthState.UNHEALTHY,
                        checked=True,
                        detail=f"manifest check failed: {type(exc).__name__}",
                    )
                )
        else:
            components.append(
                HealthComponentStatus(
                    component="constitution_manifest",
                    state=HealthState.NOT_CHECKED,
                    checked=False,
                )
            )

        return HealthSnapshot(
            snapshot_id=new_id(SNAPSHOT_PREFIX),
            checked_at=utc_now(),
            components=tuple(components),
        )


class StaticHealthSnapshotProvider(HealthSnapshotProviderPort):
    """Test helper that returns a prebuilt snapshot (still measured by the
    test author; never invents HEALTHY for unchecked components)."""

    def __init__(self, snapshot: HealthSnapshot) -> None:
        self._snapshot = snapshot

    def capture(self) -> HealthSnapshot:
        return self._snapshot
