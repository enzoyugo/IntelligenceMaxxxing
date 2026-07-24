"""Bridge token auth — fail-closed, no functional default secret."""

from __future__ import annotations

import hmac
import os

from fastapi import status
from fastapi.responses import JSONResponse

from intelligence_maxxxing.config import EngineSettings


def configured_bridge_token() -> str | None:
    """Require IM_BRIDGE_TOKEN or IM_TRADING_BRIDGE_TOKEN from environment.

    No hardcoded default. Empty/missing ⇒ writes disabled for remote callers.
    """
    for key in ("IM_BRIDGE_TOKEN", "IM_TRADING_BRIDGE_TOKEN"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


def bridge_token_ok(token: str | None) -> bool:
    expected = configured_bridge_token()
    if not expected or not token:
        return False
    return hmac.compare_digest(str(token), str(expected))


def auth_denied_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "ok": False,
            "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bridge token required"},
        },
    )


def authorize_bridge_write(
    token: str | None,
    settings: EngineSettings,
    *,
    allow_loopback_bypass: bool = False,
    is_loopback: bool = False,
) -> JSONResponse | None:
    """Return None if authorized, else 401 JSONResponse.

    Bypass only when:
    - ENGINE_ENV=test, or
    - IM_BRIDGE_AUTH_BYPASS=1 explicitly set, or
    - allow_loopback_bypass and is_loopback and IM_BRIDGE_LOOPBACK_BYPASS=1.
    Development alone does NOT bypass remote auth.
    """
    if bridge_token_ok(token):
        return None
    if settings.engine_env == "test":
        return None
    if (os.environ.get("IM_BRIDGE_AUTH_BYPASS") or "").strip() == "1":
        return None
    if (
        allow_loopback_bypass
        and is_loopback
        and (os.environ.get("IM_BRIDGE_LOOPBACK_BYPASS") or "").strip() == "1"
    ):
        return None
    # Missing configured token ⇒ fail closed for writes.
    return auth_denied_response()
