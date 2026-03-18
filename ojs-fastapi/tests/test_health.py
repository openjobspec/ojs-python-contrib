"""Tests for OJS FastAPI health check router."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from ojs_fastapi.depends import OJSPlugin  # noqa: E402
from ojs_fastapi.health import HealthResponse, create_health_router  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeQueue:
    """Minimal stand-in for an OJS Queue object."""

    name: str


def _make_mock_client() -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _build_app(plugin: OJSPlugin, mock_client: AsyncMock, *, prefix: str = "/ojs") -> FastAPI:
    app = FastAPI()
    plugin._client = mock_client
    app.state.ojs_plugin = plugin
    router = create_health_router(prefix=prefix)
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint_healthy() -> None:
    """GET /ojs/health should return healthy status when OJS is reachable."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_client.list_queues = AsyncMock(return_value=[FakeQueue("default"), FakeQueue("email")])

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ojs/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["ojs_url"] == "http://localhost:8080"
        assert len(data["queues"]) == 2
        assert data["worker_running"] is False


@pytest.mark.asyncio
async def test_health_endpoint_unhealthy() -> None:
    """GET /ojs/health should return unhealthy status when OJS is unreachable."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_client.list_queues = AsyncMock(side_effect=ConnectionError("refused"))

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ojs/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unhealthy"
        assert data["error"] == "refused"


@pytest.mark.asyncio
async def test_status_endpoint() -> None:
    """GET /ojs/status should return detailed queue stats and config."""
    plugin = OJSPlugin(url="http://localhost:8080", queues=["default", "email"], concurrency=5)
    mock_client = _make_mock_client()
    mock_client.list_queues = AsyncMock(return_value=[FakeQueue("default")])
    mock_client.queue_stats = AsyncMock(return_value={"size": 10, "active": 2})

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/ojs/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ojs_url"] == "http://localhost:8080"
        assert data["configured_queues"] == ["default", "email"]
        assert data["concurrency"] == 5
        assert len(data["queues"]) == 1
        assert data["queues"][0]["name"] == "default"
        assert data["queues"][0]["stats"] == {"size": 10, "active": 2}


@pytest.mark.asyncio
async def test_custom_prefix() -> None:
    """create_health_router should respect custom prefix."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_client.list_queues = AsyncMock(return_value=[])

    app = _build_app(plugin, mock_client, prefix="/api/v1/ojs")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/ojs/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


def test_health_response_model() -> None:
    """HealthResponse model should serialize correctly."""
    resp = HealthResponse(
        status="healthy",
        ojs_url="http://localhost:8080",
        queues=[{"name": "default"}],
        worker_running=True,
    )
    data = resp.model_dump()
    assert data["status"] == "healthy"
    assert data["ojs_url"] == "http://localhost:8080"
    assert data["worker_running"] is True
    assert data["error"] is None
