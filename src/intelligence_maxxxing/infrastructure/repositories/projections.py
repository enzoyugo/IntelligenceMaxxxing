"""SQLAlchemy accepted_observations projection and checkpoints.

The projection is derived state: it may be deleted and rebuilt from
engine_events. Checkpoints are a documented exception to append-only.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from intelligence_maxxxing.application.ports import (
    ObservationListFilters,
    ProjectedObservation,
    ProjectionCheckpoint,
    ProjectionStorePort,
)
from intelligence_maxxxing.infrastructure.database.tables import (
    AcceptedObservationRow,
    AcceptedObservationShadowRow,
    ProjectionCheckpointRow,
)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _as_utc_opt(value: datetime | None) -> datetime | None:
    return None if value is None else _as_utc(value)


class SqlAlchemyProjectionStore(ProjectionStorePort):
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_observation(self, row: ProjectedObservation) -> None:
        existing = self._session.get(AcceptedObservationRow, row.observation_id)
        if existing is None:
            self._session.add(_to_row(row))
            return
        # Idempotent replay: overwrite with the same deterministic values.
        existing.global_position = row.global_position
        existing.event_id = row.event_id
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.domain_pack = row.domain_pack
        existing.schema_version = row.schema_version
        existing.subject = row.subject
        existing.statement = row.statement
        existing.knowledge_class = row.knowledge_class
        existing.unknown_reason = row.unknown_reason
        existing.observed_by = row.observed_by
        existing.context = dict(row.context)
        existing.source_ids = list(row.source_ids)
        existing.meta = dict(row.metadata)
        existing.occurred_at = row.occurred_at
        existing.created_at = row.created_at
        existing.audit_id = row.audit_id

    def get_observation(
        self, owner_id: str, application_id: str, observation_id: str
    ) -> ProjectedObservation | None:
        stmt = select(AcceptedObservationRow).where(
            AcceptedObservationRow.observation_id == observation_id,
            AcceptedObservationRow.owner_id == owner_id,
            AcceptedObservationRow.application_id == application_id,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _from_row(row)

    def list_observations(
        self, owner_id: str, application_id: str, filters: ObservationListFilters
    ) -> Sequence[ProjectedObservation]:
        stmt = select(AcceptedObservationRow).where(
            AcceptedObservationRow.owner_id == owner_id,
            AcceptedObservationRow.application_id == application_id,
        )
        if filters.domain_pack is not None:
            stmt = stmt.where(AcceptedObservationRow.domain_pack == filters.domain_pack)
        if filters.occurred_from is not None:
            stmt = stmt.where(AcceptedObservationRow.occurred_at >= filters.occurred_from)
        if filters.occurred_to is not None:
            stmt = stmt.where(AcceptedObservationRow.occurred_at <= filters.occurred_to)
        if filters.after_position is not None:
            stmt = stmt.where(AcceptedObservationRow.global_position > filters.after_position)
        stmt = stmt.order_by(AcceptedObservationRow.global_position).limit(filters.limit)
        return [_from_row(r) for r in self._session.scalars(stmt)]

    def list_all_observations(self) -> Sequence[ProjectedObservation]:
        # autoflush is disabled; reflect any pending live upserts (resume path).
        self._session.flush()
        stmt = select(AcceptedObservationRow).order_by(AcceptedObservationRow.global_position)
        return [_from_row(r) for r in self._session.scalars(stmt)]

    def delete_all_observations(self) -> int:
        result = self._session.execute(delete(AcceptedObservationRow))
        return int(getattr(result, "rowcount", 0) or 0)

    # ---- shadow / staging -------------------------------------------------

    def upsert_shadow_observation(self, row: ProjectedObservation) -> None:
        existing = self._session.get(AcceptedObservationShadowRow, row.observation_id)
        if existing is None:
            self._session.add(_to_shadow_row(row))
            return
        existing.global_position = row.global_position
        existing.event_id = row.event_id
        existing.tenant_id = row.tenant_id
        existing.owner_id = row.owner_id
        existing.application_id = row.application_id
        existing.domain_pack = row.domain_pack
        existing.schema_version = row.schema_version
        existing.subject = row.subject
        existing.statement = row.statement
        existing.knowledge_class = row.knowledge_class
        existing.unknown_reason = row.unknown_reason
        existing.observed_by = row.observed_by
        existing.context = dict(row.context)
        existing.source_ids = list(row.source_ids)
        existing.meta = dict(row.metadata)
        existing.occurred_at = row.occurred_at
        existing.created_at = row.created_at
        existing.audit_id = row.audit_id

    def list_all_shadow_observations(self) -> Sequence[ProjectedObservation]:
        # The session runs with autoflush disabled; flush pending shadow
        # upserts so this read reflects the in-progress build.
        self._session.flush()
        stmt = select(AcceptedObservationShadowRow).order_by(
            AcceptedObservationShadowRow.global_position
        )
        return [_from_shadow_row(r) for r in self._session.scalars(stmt)]

    def delete_all_shadow_observations(self) -> int:
        # Flush first so pending (autoflush-disabled) shadow upserts are visible
        # to the bulk delete; otherwise they would be flushed AFTER it on commit
        # and survive. This keeps a quarantined build from leaving stray rows.
        self._session.flush()
        result = self._session.execute(
            delete(AcceptedObservationShadowRow),
            execution_options={"synchronize_session": "fetch"},
        )
        self._session.flush()
        return int(getattr(result, "rowcount", 0) or 0)

    def promote_shadow_observations(self) -> int:
        """Atomically replace live rows with the shadow set (same transaction).

        Live is emptied and refilled from the shadow rows, then shadow is
        cleared. All of this participates in the caller's transaction, so the
        swap is atomic: it commits or rolls back as one unit.
        """
        # autoflush is disabled; make sure pending shadow upserts are persisted
        # before we read them, and read shadow BEFORE clearing live.
        self._session.flush()
        shadow_rows = list(
            self._session.scalars(
                select(AcceptedObservationShadowRow).order_by(
                    AcceptedObservationShadowRow.global_position
                )
            )
        )
        self._session.execute(delete(AcceptedObservationRow))
        self._session.flush()
        promoted = 0
        for shadow in shadow_rows:
            self._session.add(_shadow_to_live(shadow))
            promoted += 1
        self._session.flush()
        self._session.execute(delete(AcceptedObservationShadowRow))
        self._session.flush()
        return promoted

    def get_checkpoint(
        self, projection_name: str, projection_version: str
    ) -> ProjectionCheckpoint | None:
        stmt = select(ProjectionCheckpointRow).where(
            ProjectionCheckpointRow.projection_name == projection_name,
            ProjectionCheckpointRow.projection_version == projection_version,
        )
        row = self._session.scalars(stmt).first()
        return None if row is None else _checkpoint(row)

    def save_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        stmt = select(ProjectionCheckpointRow).where(
            ProjectionCheckpointRow.projection_name == checkpoint.projection_name,
            ProjectionCheckpointRow.projection_version == checkpoint.projection_version,
            ProjectionCheckpointRow.owner_scope == checkpoint.owner_scope,
            ProjectionCheckpointRow.application_scope == checkpoint.application_scope,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            self._session.add(
                ProjectionCheckpointRow(
                    projection_name=checkpoint.projection_name,
                    projection_version=checkpoint.projection_version,
                    owner_scope=checkpoint.owner_scope,
                    application_scope=checkpoint.application_scope,
                    last_global_position=checkpoint.last_global_position,
                    last_event_id=checkpoint.last_event_id,
                    updated_at=checkpoint.updated_at,
                    status=checkpoint.status,
                    checksum=checkpoint.checksum,
                )
            )
            return
        row.last_global_position = checkpoint.last_global_position
        row.last_event_id = checkpoint.last_event_id
        row.updated_at = checkpoint.updated_at
        row.status = checkpoint.status
        row.checksum = checkpoint.checksum

    def delete_checkpoint(self, projection_name: str, projection_version: str) -> None:
        self._session.execute(
            delete(ProjectionCheckpointRow).where(
                ProjectionCheckpointRow.projection_name == projection_name,
                ProjectionCheckpointRow.projection_version == projection_version,
            )
        )


def _to_row(row: ProjectedObservation) -> AcceptedObservationRow:
    return AcceptedObservationRow(
        observation_id=row.observation_id,
        global_position=row.global_position,
        event_id=row.event_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        schema_version=row.schema_version,
        subject=row.subject,
        statement=row.statement,
        knowledge_class=row.knowledge_class,
        unknown_reason=row.unknown_reason,
        observed_by=row.observed_by,
        context=dict(row.context),
        source_ids=list(row.source_ids),
        meta=dict(row.metadata),
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        audit_id=row.audit_id,
    )


def _to_shadow_row(row: ProjectedObservation) -> AcceptedObservationShadowRow:
    return AcceptedObservationShadowRow(
        observation_id=row.observation_id,
        global_position=row.global_position,
        event_id=row.event_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        schema_version=row.schema_version,
        subject=row.subject,
        statement=row.statement,
        knowledge_class=row.knowledge_class,
        unknown_reason=row.unknown_reason,
        observed_by=row.observed_by,
        context=dict(row.context),
        source_ids=list(row.source_ids),
        meta=dict(row.metadata),
        occurred_at=row.occurred_at,
        created_at=row.created_at,
        audit_id=row.audit_id,
    )


def _shadow_to_live(shadow: AcceptedObservationShadowRow) -> AcceptedObservationRow:
    return AcceptedObservationRow(
        observation_id=shadow.observation_id,
        global_position=shadow.global_position,
        event_id=shadow.event_id,
        tenant_id=shadow.tenant_id,
        owner_id=shadow.owner_id,
        application_id=shadow.application_id,
        domain_pack=shadow.domain_pack,
        schema_version=shadow.schema_version,
        subject=shadow.subject,
        statement=shadow.statement,
        knowledge_class=shadow.knowledge_class,
        unknown_reason=shadow.unknown_reason,
        observed_by=shadow.observed_by,
        context=dict(shadow.context),
        source_ids=list(shadow.source_ids),
        meta=dict(shadow.meta),
        occurred_at=shadow.occurred_at,
        created_at=shadow.created_at,
        audit_id=shadow.audit_id,
    )


def _from_shadow_row(row: AcceptedObservationShadowRow) -> ProjectedObservation:
    return ProjectedObservation(
        observation_id=row.observation_id,
        global_position=row.global_position,
        event_id=row.event_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        schema_version=row.schema_version,
        subject=row.subject,
        statement=row.statement,
        knowledge_class=row.knowledge_class,
        unknown_reason=row.unknown_reason,
        observed_by=row.observed_by,
        context=dict(row.context),
        source_ids=tuple(row.source_ids),
        metadata=dict(row.meta),
        occurred_at=_as_utc_opt(row.occurred_at),
        created_at=_as_utc(row.created_at),
        audit_id=row.audit_id,
    )


def _from_row(row: AcceptedObservationRow) -> ProjectedObservation:
    return ProjectedObservation(
        observation_id=row.observation_id,
        global_position=row.global_position,
        event_id=row.event_id,
        tenant_id=row.tenant_id,
        owner_id=row.owner_id,
        application_id=row.application_id,
        domain_pack=row.domain_pack,
        schema_version=row.schema_version,
        subject=row.subject,
        statement=row.statement,
        knowledge_class=row.knowledge_class,
        unknown_reason=row.unknown_reason,
        observed_by=row.observed_by,
        context=dict(row.context),
        source_ids=tuple(row.source_ids),
        metadata=dict(row.meta),
        occurred_at=_as_utc_opt(row.occurred_at),
        created_at=_as_utc(row.created_at),
        audit_id=row.audit_id,
    )


def _checkpoint(row: ProjectionCheckpointRow) -> ProjectionCheckpoint:
    return ProjectionCheckpoint(
        projection_name=row.projection_name,
        projection_version=row.projection_version,
        owner_scope=row.owner_scope,
        application_scope=row.application_scope,
        last_global_position=row.last_global_position,
        last_event_id=row.last_event_id,
        updated_at=_as_utc(row.updated_at),
        status=row.status,
        checksum=row.checksum,
    )
