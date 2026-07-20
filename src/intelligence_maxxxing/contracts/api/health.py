"""Public contract for GET /api/v1/health."""

from pydantic import BaseModel, ConfigDict


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    engine_version: str
    constitution_version: str
    commit_sha: str | None = None
    api_version: str | None = None
    database: str | None = None
    migration_revision: str | None = None
    wellbeing_active: str | None = None
    wellbeing_shadow: str | None = None
