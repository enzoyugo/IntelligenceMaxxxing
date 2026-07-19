"""Request ID and structured request logging middleware."""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from intelligence_maxxxing.domain.common.identifiers import REQUEST_PREFIX, new_id
from intelligence_maxxxing.observability import get_logger

logger = get_logger("intelligence_maxxxing.api.request")


def register_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = new_id(REQUEST_PREFIX)
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code: int | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "request completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "engine_version": request.app.state.settings.engine_version,
                },
            )
        response.headers["X-Request-Id"] = request_id
        return response
