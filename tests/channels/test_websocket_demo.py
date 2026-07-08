"""Tests for DEMO mode: config validator, bootstrap bypass, and abuse caps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from nanobot.channels.websocket import (
    _DEMO_LIMIT_MESSAGE,
    WebSocketChannel,
    WebSocketConfig,
    _demo_env_int,
    _DemoLimiter,
)
from nanobot.webui.gateway_services import build_gateway_services

# --- Config validator -------------------------------------------------------


def test_wildcard_host_allowed_when_demo_without_token():
    cfg = WebSocketConfig.model_validate(
        {"host": "0.0.0.0", "demo": True, "websocketRequiresToken": True}
    )
    assert cfg.demo is True
    assert cfg.token == ""


def test_wildcard_host_rejected_when_not_demo_without_token():
    with pytest.raises(ValidationError):
        WebSocketConfig.model_validate({"host": "0.0.0.0"})


def test_demo_defaults_false():
    assert WebSocketConfig().demo is False


# --- Env parsing ------------------------------------------------------------


def test_demo_env_int_unset_returns_default(monkeypatch):
    monkeypatch.delenv("X_DEMO_TEST", raising=False)
    assert _demo_env_int("X_DEMO_TEST", 10) == 10


def test_demo_env_int_parses_value(monkeypatch):
    monkeypatch.setenv("X_DEMO_TEST", "3")
    assert _demo_env_int("X_DEMO_TEST", 10) == 3


def test_demo_env_int_zero_disables(monkeypatch):
    monkeypatch.setenv("X_DEMO_TEST", "0")
    assert _demo_env_int("X_DEMO_TEST", 10) == 0


def test_demo_env_int_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("X_DEMO_TEST", "abc")
    assert _demo_env_int("X_DEMO_TEST", 10) == 10


# --- Rate limiter + per-session cap -----------------------------------------


def test_limiter_rate_limit_trips_within_window():
    t = [0.0]
    lim = _DemoLimiter(2, 0, now=lambda: t[0])
    assert lim.check() is True
    assert lim.check() is True
    assert lim.check() is False  # third within the same minute is blocked
    t[0] = 61.0  # window slides forward
    assert lim.check() is True


def test_limiter_session_cap_trips():
    lim = _DemoLimiter(0, 3, now=lambda: 0.0)
    assert [lim.check() for _ in range(4)] == [True, True, True, False]


def test_limiter_unlimited_when_zero():
    lim = _DemoLimiter(0, 0, now=lambda: 0.0)
    assert all(lim.check() for _ in range(100))


def test_limit_message_is_friendly():
    assert "deploy your own nanobot" in _DEMO_LIMIT_MESSAGE.lower()


# --- Bootstrap demo bypass --------------------------------------------------


class _FakeConn:
    def __init__(self, remote: tuple[str, int] | None):
        self.remote_address = remote


class _FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None):
        self.headers = headers or {}


def _services(cfg: dict[str, Any], tmp_path: Path):
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    return build_gateway_services(
        config=WebSocketConfig.model_validate(cfg),
        bus=bus,
        session_manager=None,
        static_dist_path=None,
        workspace_path=tmp_path,
        default_restrict_to_workspace=False,
        runtime_model_name=lambda: "anthropic/claude-haiku-4-5",
        runtime_surface="browser",
        runtime_capabilities_overrides=None,
        cron_service=None,
        local_trigger_store=None,
        cron_pending_job_ids=None,
        local_trigger_pending_ids=None,
    )


def _handler(cfg: dict[str, Any], tmp_path: Path):
    return _services(cfg, tmp_path).http


def _channel(cfg: dict[str, Any], tmp_path: Path) -> WebSocketChannel:
    validated = WebSocketConfig.model_validate(cfg)
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()
    services = _services(cfg, tmp_path)
    return WebSocketChannel(validated, bus, gateway=services)


def test_bootstrap_demo_bypass_remote_no_secret(tmp_path):
    handler = _handler(
        {"host": "0.0.0.0", "demo": True, "websocketRequiresToken": True},
        tmp_path,
    )
    conn = _FakeConn(("203.0.113.9", 5555))  # non-localhost
    resp = handler._handle_bootstrap(conn, _FakeRequest())
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["demo"] is True
    assert body["token"]


def test_bootstrap_non_demo_remote_no_secret_is_forbidden(tmp_path):
    handler = _handler(
        {"host": "127.0.0.1", "websocketRequiresToken": False},
        tmp_path,
    )
    conn = _FakeConn(("203.0.113.9", 5555))  # non-localhost, no secret set
    resp = handler._handle_bootstrap(conn, _FakeRequest())
    assert resp.status_code == 403


def test_bootstrap_non_demo_with_secret_requires_header(tmp_path):
    handler = _handler(
        {"host": "0.0.0.0", "token": "s3cr3t-token", "websocketRequiresToken": True},
        tmp_path,
    )
    conn = _FakeConn(("203.0.113.9", 5555))
    # No auth header supplied → unauthorized.
    resp = handler._handle_bootstrap(conn, _FakeRequest())
    assert resp.status_code == 401
    # Correct secret → 200 and demo is False.
    ok = handler._handle_bootstrap(
        conn, _FakeRequest({"X-Nanobot-Auth": "s3cr3t-token"})
    )
    assert ok.status_code == 200
    assert json.loads(ok.body)["demo"] is False


# --- Channel limiter wiring + friendly stop ---------------------------------


def test_new_demo_limiter_none_when_not_demo(tmp_path):
    ch = _channel({"host": "127.0.0.1", "websocketRequiresToken": False}, tmp_path)
    assert ch._new_demo_limiter() is None


def test_new_demo_limiter_built_when_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_RATE_LIMIT_PER_MINUTE", "5")
    monkeypatch.setenv("DEMO_MAX_MESSAGES_PER_SESSION", "7")
    ch = _channel(
        {"host": "0.0.0.0", "demo": True, "websocketRequiresToken": True}, tmp_path
    )
    lim = ch._new_demo_limiter()
    assert isinstance(lim, _DemoLimiter)
    assert lim._rate == 5
    assert lim._max == 7


async def test_send_demo_limit_reply_emits_message_and_turn_end(tmp_path):
    ch = _channel(
        {"host": "0.0.0.0", "demo": True, "websocketRequiresToken": True}, tmp_path
    )
    sent: list[dict[str, Any]] = []

    class _Conn:
        async def send(self, raw: str) -> None:
            sent.append(json.loads(raw))

    await ch._send_demo_limit_reply(_Conn(), "chat-123")
    assert sent[0]["event"] == "message"
    assert sent[0]["text"] == _DEMO_LIMIT_MESSAGE
    assert sent[0]["chat_id"] == "chat-123"
    assert sent[1]["event"] == "turn_end"
