"""P1-E: bridge auth fail-closed — no functional default token."""

from __future__ import annotations

import os

from intelligence_maxxxing.api.bridge_auth_v1 import (
    authorize_bridge_write,
    bridge_token_ok,
    configured_bridge_token,
)
from intelligence_maxxxing.config import EngineSettings


def test_default_token_does_not_exist(monkeypatch) -> None:
    monkeypatch.delenv("IM_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("IM_TRADING_BRIDGE_TOKEN", raising=False)
    assert configured_bridge_token() is None
    assert bridge_token_ok("tmx-im-local-bridge-v1") is False


def test_missing_bridge_token_disables_remote_write(monkeypatch) -> None:
    monkeypatch.delenv("IM_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("IM_TRADING_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("IM_BRIDGE_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("ENGINE_ENV", "production")
    settings = EngineSettings()
    denied = authorize_bridge_write(None, settings)
    assert denied is not None
    assert denied.status_code == 401


def test_valid_token_allows_expected_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("IM_BRIDGE_TOKEN", "secret-test-token")
    monkeypatch.setenv("ENGINE_ENV", "production")
    assert bridge_token_ok("secret-test-token") is True
    settings = EngineSettings()
    assert authorize_bridge_write("secret-test-token", settings) is None


def test_development_mode_does_not_bypass_remote_auth(monkeypatch) -> None:
    monkeypatch.delenv("IM_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("IM_TRADING_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("IM_BRIDGE_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("ENGINE_ENV", "development")
    settings = EngineSettings()
    denied = authorize_bridge_write(None, settings)
    assert denied is not None


def test_invalid_token_returns_401_or_403(monkeypatch) -> None:
    monkeypatch.setenv("IM_BRIDGE_TOKEN", "secret-test-token")
    monkeypatch.delenv("IM_BRIDGE_AUTH_BYPASS", raising=False)
    monkeypatch.setenv("ENGINE_ENV", "production")
    settings = EngineSettings()
    denied = authorize_bridge_write("wrong", settings)
    assert denied is not None
    assert denied.status_code in {401, 403}
