"""Tests for OJS FastAPI dependency injection edge cases."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from fastapi import Depends, FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from ojs_fastapi import OJSPlugin, get_ojs_client  # noqa: E402
from ojs_fastapi.models import EnqueueResponse  # noqa: E402


@dataclass
class FakeJob:
    id: str = "01912345-6789-7abc-def0-123456789abc"
    type: str = "email.send"
    state: str = "available"
    queue: str = "default"
    args: list[Any] | None = None
    meta: dict[str, Any] | None = None


class TestDependencyInjection:
    """Tests for dependency injection of OJS client into endpoints."""

    @pytest.mark.asyncio
    async def test_multiple_endpoints_share_client(self) -> None:
        plugin = OJSPlugin(url="http://localhost:8080")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.enqueue = AsyncMock(return_value=FakeJob())
        plugin._client = mock_client

        app = FastAPI()
        app.state.ojs_plugin = plugin

        @app.post("/jobs")
        async def create_job(client: Any = Depends(get_ojs_client)) -> dict[str, str]:
            job = await client.enqueue("email.send", [])
            return {"job_id": job.id}

        @app.post("/batch")
        async def batch_jobs(client: Any = Depends(get_ojs_client)) -> dict[str, str]:
            job = await client.enqueue("batch.run", [])
            return {"job_id": job.id}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r1 = await ac.post("/jobs", json={})
            r2 = await ac.post("/batch", json={})
            assert r1.status_code == 200
            assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_plugin_custom_config(self) -> None:
        plugin = OJSPlugin(
            url="http://custom:9090",
            queues=["high", "low"],
            concurrency=20,
            poll_interval=5.0,
        )
        assert plugin.url == "http://custom:9090"
        assert plugin.queues == ["high", "low"]
        assert plugin.concurrency == 20
        assert plugin.poll_interval == 5.0

    @pytest.mark.asyncio
    async def test_client_injection_with_custom_url(self) -> None:
        plugin = OJSPlugin(url="http://custom:9090")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.enqueue = AsyncMock(return_value=FakeJob(queue="custom"))
        plugin._client = mock_client

        app = FastAPI()
        app.state.ojs_plugin = plugin

        @app.post("/jobs")
        async def create_job(client: Any = Depends(get_ojs_client)) -> dict[str, str]:
            job = await client.enqueue("test", [])
            return {"queue": job.queue}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/jobs", json={})
            assert resp.json()["queue"] == "custom"
