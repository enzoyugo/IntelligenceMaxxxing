"""Measure Stage 1 local performance bounds (not a hard gate)."""

from __future__ import annotations

import statistics
import tempfile
import time
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from tests.conftest import valid_observation_payload
from tests.fixtures.identity import bootstrap_test_identity

from intelligence_maxxxing import API_VERSION
from intelligence_maxxxing.api.app import create_app
from intelligence_maxxxing.application.use_cases.integrity import (
    IntegrityVerificationService,
    NoOpIntegrityViolationHook,
)
from intelligence_maxxxing.application.use_cases.projections import ProjectionRebuildService
from intelligence_maxxxing.config import EngineSettings
from intelligence_maxxxing.infrastructure.database import Base
from intelligence_maxxxing.infrastructure.health import (
    MeasuredHealthSnapshotProvider,
    SqlAlchemyDatabaseHealth,
)
from intelligence_maxxxing.infrastructure.repositories import SqlAlchemyUnitOfWork


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((p / 100) * (len(ordered) - 1))))
    return ordered[idx]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imx_bench_"))
    db_url = f"sqlite:///{tmp / 'bench.sqlite3'}"
    settings = EngineSettings(
        ENGINE_ENV="test",
        ENGINE_HOST="127.0.0.1",
        ENGINE_PORT=8100,
        ENGINE_VERSION="0.1.0",
        CONSTITUTION_VERSION="1.1",
        DATABASE_URL=db_url,
        LOG_LEVEL="WARNING",
        _env_file=None,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.db_engine)
    identity = bootstrap_test_identity(app)

    submit_ms: list[float] = []
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers.update(identity.auth_header)
        for _ in range(50):
            start = time.perf_counter()
            response = client.post(
                "/api/v1/observations",
                json=valid_observation_payload(),
                headers={"Idempotency-Key": f"bench-{uuid.uuid4().hex}"},
            )
            submit_ms.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 201

        list_ms: list[float] = []
        for _ in range(50):
            start = time.perf_counter()
            response = client.get("/api/v1/observations")
            list_ms.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 200

    # Seed up to ~1000 observation events for replay/integrity timing.
    with TestClient(app, raise_server_exceptions=False) as client:
        client.headers.update(identity.auth_header)
        for _ in range(950):
            client.post(
                "/api/v1/observations",
                json=valid_observation_payload(),
                headers={"Idempotency-Key": f"bench2-{uuid.uuid4().hex}"},
            )

    health = MeasuredHealthSnapshotProvider(
        SqlAlchemyDatabaseHealth(app.state.db_engine), check_manifest=False
    )
    start = time.perf_counter()
    rebuild = ProjectionRebuildService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version="0.1.0",
        api_version=API_VERSION,
        health_provider=health,
    ).rebuild(from_scratch=True)
    rebuild_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    report = IntegrityVerificationService(
        uow=SqlAlchemyUnitOfWork(app.state.session_factory),
        engine_version="0.1.0",
        api_version=API_VERSION,
        health_provider=health,
        violation_hook=NoOpIntegrityViolationHook(),
    ).verify(mode="FULL")
    integrity_ms = (time.perf_counter() - start) * 1000

    # Concurrent idempotency timing (same payload).
    from concurrent.futures import ThreadPoolExecutor, as_completed

    key = f"bench-concurrent-{uuid.uuid4().hex}"
    payload = valid_observation_payload()
    start = time.perf_counter()

    def worker() -> int:
        with TestClient(app, raise_server_exceptions=False) as client:
            client.headers.update(identity.auth_header)
            return client.post(
                "/api/v1/observations",
                json=payload,
                headers={"Idempotency-Key": key},
            ).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = [f.result() for f in as_completed([pool.submit(worker) for _ in range(8)])]
    concurrent_ms = (time.perf_counter() - start) * 1000

    print("STAGE_1_BENCHMARKS")
    print(f"submit_observation_p50_ms={_pct(submit_ms, 50):.2f}")
    print(f"submit_observation_p95_ms={_pct(submit_ms, 95):.2f}")
    print(f"list_observations_p50_ms={_pct(list_ms, 50):.2f}")
    print(f"list_observations_p95_ms={_pct(list_ms, 95):.2f}")
    print(f"replay_events_scanned={rebuild.events_scanned}")
    print(f"projection_rebuild_ms={rebuild_ms:.2f}")
    print(f"integrity_events_checked={report.events_checked}")
    print(f"integrity_check_ms={integrity_ms:.2f}")
    print(f"concurrent_idempotency_ms={concurrent_ms:.2f}")
    print(f"concurrent_idempotency_statuses={sorted(codes)}")
    print(f"submit_mean_ms={statistics.mean(submit_ms):.2f}")
    app.state.db_engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
