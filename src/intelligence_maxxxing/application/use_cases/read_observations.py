"""Owner-scoped observation reads, served from the accepted_observations
projection (never by recomposing the full ledger per request)."""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.application.auth.service import AuthContext
from intelligence_maxxxing.application.errors import ObservationNotFoundError
from intelligence_maxxxing.application.ports import (
    ObservationListFilters,
    ProjectedObservation,
    ProjectionCheckpoint,
    UnitOfWorkPort,
)
from intelligence_maxxxing.application.use_cases.projections import (
    ACCEPTED_OBSERVATIONS_PROJECTION,
    ACCEPTED_OBSERVATIONS_VERSION,
)


class ObservationPage(BaseModel):
    """One deterministic page plus projection freshness metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: tuple[ProjectedObservation, ...]
    next_cursor: int | None
    projection_name: str
    projection_version: str
    projection_position: int | None
    projection_updated_at: str | None


class GetObservationUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, observation_id: str, auth: AuthContext) -> ProjectedObservation:
        with self._uow as uow:
            row = uow.projections.get_observation(
                auth.owner_id, auth.application_id, observation_id
            )
            uow.commit()
        if row is None:
            raise ObservationNotFoundError(f"observation not found: {observation_id}")
        return row


class ListObservationsUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, filters: ObservationListFilters, auth: AuthContext) -> ObservationPage:
        with self._uow as uow:
            rows: Sequence[ProjectedObservation] = uow.projections.list_observations(
                auth.owner_id, auth.application_id, filters
            )
            checkpoint: ProjectionCheckpoint | None = uow.projections.get_checkpoint(
                ACCEPTED_OBSERVATIONS_PROJECTION, ACCEPTED_OBSERVATIONS_VERSION
            )
            uow.commit()
        next_cursor = rows[-1].global_position if len(rows) == filters.limit and rows else None
        return ObservationPage(
            items=tuple(rows),
            next_cursor=next_cursor,
            projection_name=ACCEPTED_OBSERVATIONS_PROJECTION,
            projection_version=ACCEPTED_OBSERVATIONS_VERSION,
            projection_position=checkpoint.last_global_position if checkpoint else None,
            projection_updated_at=(
                checkpoint.updated_at.isoformat() if checkpoint is not None else None
            ),
        )
