"""Environment-driven settings. Secrets never live in code."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EngineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    engine_env: str = Field(default="development", alias="ENGINE_ENV")
    engine_host: str = Field(default="127.0.0.1", alias="ENGINE_HOST")
    engine_port: int = Field(default=8100, alias="ENGINE_PORT")
    engine_version: str = Field(default="0.1.0", alias="ENGINE_VERSION")
    constitution_version: str = Field(default="1.1", alias="CONSTITUTION_VERSION")
    database_url: str = Field(
        default="postgresql+psycopg://intelligence:intelligence@127.0.0.1:5432/intelligence_maxxxing",
        alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Migration safety (all default to safe/off). See MIGRATION_SAFETY.md.
    engine_destructive_migrations_allowed: bool = Field(
        default=False, alias="ENGINE_DESTRUCTIVE_MIGRATIONS_ALLOWED"
    )
    engine_maintenance_mode: bool = Field(default=False, alias="ENGINE_MAINTENANCE_MODE")
    engine_confirmed_backup_id: str | None = Field(default=None, alias="ENGINE_CONFIRMED_BACKUP_ID")


@lru_cache(maxsize=1)
def get_settings() -> EngineSettings:
    return EngineSettings()
