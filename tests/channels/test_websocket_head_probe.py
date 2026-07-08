"""The WebSocket channel must answer non-GET HTTP probes cleanly.

A hosted deploy's load balancer / uptime monitor probes the public port. The
websockets handshake parser only accepts GET, so a HEAD probe used to abort the
connection (client sees 502) and log a full traceback at ERROR once per probe —
flooding the logs. The channel now sniffs the first request line: GET passes
through (WS upgrades + WebUI HTTP), HEAD gets an empty 200, other methods get
405, and probes are closed without an ERROR log.
"""

import asyncio
import functools
import logging
import random
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from nanobot.channels.websocket import WebSocketChannel, WebSocketConfig
from nanobot.webui.gateway_services import build_gateway_services


def _free_port() -> int:
    for _ in range(100):
        port = random.randint(30_000, 60_000)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("could not find a free localhost port")


def _channel(bus: Any, port: int) -> WebSocketChannel:
    cfg: dict[str, Any] = {
        "enabled": True,
        "allowFrom": ["*"],
        "host": "127.0.0.1",
        "port": port,
        "path": "/",
        "websocketRequiresToken": False,
    }
    config = WebSocketConfig.model_validate(cfg)
    gateway = build_gateway_services(
        config=config,
        bus=bus,
        session_manager=None,
        static_dist_path=None,
        workspace_path=None,
        default_restrict_to_workspace=False,
        runtime_model_name=None,
        runtime_surface="browser",
        runtime_capabilities_overrides=None,
    )
    return WebSocketChannel(cfg, bus, gateway=gateway)


async def _request(method: str, url: str) -> httpx.Response:
    return await asyncio.to_thread(
        functools.partial(httpx.request, method, url, timeout=5.0, trust_env=False)
    )


@pytest.fixture()
def bus() -> MagicMock:
    b = MagicMock()
    b.publish_inbound = AsyncMock()
    return b


@pytest.mark.asyncio
async def test_head_probe_returns_200_and_does_not_log_error(
    bus: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    channel = _channel(bus, port)
    server_task = asyncio.create_task(channel.start())
    await asyncio.sleep(0.3)
    try:
        with caplog.at_level(logging.ERROR, logger="websockets.server"):
            # HEAD (what a health/uptime probe sends) is answered, not aborted.
            head = await _request("HEAD", f"{base}/")
            assert head.status_code == 200

            # A GET WebUI route is unaffected by the sniffing.
            boot = await _request("GET", f"{base}/webui/bootstrap")
            assert boot.status_code == 200

            # An unsupported method gets a clean 405, not a 502.
            post = await _request("POST", f"{base}/")
            assert post.status_code == 405
            assert "GET" in post.headers.get("allow", "")

        # The probe must not produce the websockets "opening handshake failed"
        # ERROR traceback that used to flood the logs.
        assert not any(
            "opening handshake failed" in record.getMessage() for record in caplog.records
        )
    finally:
        await channel.stop()
        await server_task
