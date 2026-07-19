"""Retrieve a recoverable audit record with its associated events."""

from pydantic import BaseModel, ConfigDict

from intelligence_maxxxing.application.errors import AuditNotFoundError
from intelligence_maxxxing.application.ports import UnitOfWorkPort
from intelligence_maxxxing.domain.audit.models import AuditRecord, EngineEvent


class AuditBundle(BaseModel):
    """Audit record plus the events it references; enough to reconstruct what happened."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    audit: AuditRecord
    events: tuple[EngineEvent, ...]


class GetAuditUseCase:
    def __init__(self, uow: UnitOfWorkPort) -> None:
        self._uow = uow

    def execute(self, audit_id: str) -> AuditBundle:
        with self._uow as uow:
            record = uow.audits.get_by_audit_id(audit_id)
            if record is None:
                raise AuditNotFoundError(f"audit record not found: {audit_id}")
            events = tuple(uow.events.list_by_audit_id(audit_id))
        return AuditBundle(audit=record, events=events)
