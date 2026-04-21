"""Tests for OJS FastAPI dependency injection."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock the ojs module before any ojs_fastapi imports trigger it
# ---------------------------------------------------------------------------

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from fastapi import Depends, FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from ojs_fastapi import OJSPlugin, get_ojs_client, ojs_lifespan  # noqa: E402
from ojs_fastapi.models import EnqueueResponse  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeJob:
    """Minimal stand-in for ``ojs.Job``."""

    id: str = "01912345-6789-7abc-def0-123456789abc"
    type: str = "email.send"
    state: str = "available"
    queue: str = "default"
    args: list[Any] | None = None
    meta: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.args is None:
            self.args = []
        if self.meta is None:
            self.meta = {}


def _make_mock_client() -> AsyncMock:
    """Create a mock OJS client with async context manager support."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _build_app(plugin: OJSPlugin, mock_client: AsyncMock) -> FastAPI:
    """Build a FastAPI app with OJS plugin pre-configured on state."""
    app = FastAPI()

    # Wire plugin and client directly (lifespan not triggered by ASGITransport)
    plugin._client = mock_client
    app.state.ojs_plugin = plugin

    @app.post("/jobs", response_model=EnqueueResponse)
    async def enqueue_job(
        body: dict[str, Any],
        client: Any = Depends(get_ojs_client),
    ) -> EnqueueResponse:
        job = await client.enqueue(
            body["type"],
            body.get("args", []),
            queue=body.get("queue", "default"),
            meta=body.get("meta", {}),
            priority=body.get("priority", 0),
        )
        return EnqueueResponse(
            job_id=job.id,
            type=job.type,
            state=str(job.state),
            queue=job.queue,
        )

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ojs_client_returns_client() -> None:
    """The dependency should yield the client stored on the plugin."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_client.enqueue = AsyncMock(return_value=FakeJob())

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs",
            json={"type": "email.send", "args": ["user@example.com"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data


@pytest.mark.asyncio
async def test_client_stored_on_app_state() -> None:
    """The plugin must expose the client that was wired onto app state."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_client.enqueue = AsyncMock(return_value=FakeJob())

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/jobs", json={"type": "ping", "args": []})
        assert plugin.client is mock_client
        assert app.state.ojs_plugin is plugin


@pytest.mark.asyncio
async def test_enqueue_via_endpoint() -> None:
    """POST /jobs should call client.enqueue and return the job envelope."""
    plugin = OJSPlugin(url="http://localhost:8080")
    fake_job = FakeJob(type="report.generate", queue="reports")

    mock_client = _make_mock_client()
    mock_client.enqueue = AsyncMock(return_value=fake_job)

    app = _build_app(plugin, mock_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/jobs",
            json={
                "type": "report.generate",
                "args": [42],
                "queue": "reports",
                "meta": {"requested_by": "admin"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == fake_job.id
    assert data["type"] == "report.generate"
    assert data["queue"] == "reports"

    mock_client.enqueue.assert_awaited_once_with(
        "report.generate",
        [42],
        queue="reports",
        meta={"requested_by": "admin"},
        priority=0,
    )


@pytest.mark.asyncio
async def test_lifespan_creates_client() -> None:
    """ojs_lifespan should create and store the client on the plugin."""
    plugin = OJSPlugin(url="http://localhost:8080")

    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin) as state:
        assert state["ojs_client"] is mock_client
        assert plugin.client is mock_client
        assert app.state.ojs_plugin is plugin

    # After lifespan exit, client should be cleared
    assert plugin._client is None
