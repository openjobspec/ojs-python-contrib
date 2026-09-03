"""Tests for FastAPI OJS lifespan management."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from fastapi import FastAPI  # noqa: E402

from ojs_fastapi import OJSPlugin, ojs_lifespan  # noqa: E402


def _make_mock_client() -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_lifespan_stores_plugin_on_app_state() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin):
        assert app.state.ojs_plugin is plugin


@pytest.mark.asyncio
async def test_lifespan_clears_client_on_exit() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin):
        assert plugin._client is mock_client

    assert plugin._client is None


@pytest.mark.asyncio
async def test_lifespan_yields_state_dict() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin) as state:
        assert "ojs_client" in state
        assert "ojs_worker" in state
        assert state["ojs_client"] is mock_client


@pytest.mark.asyncio
async def test_lifespan_without_plugin_raises() -> None:
    app = FastAPI()
    with pytest.raises(RuntimeError, match="No OJSPlugin provided"):
        async with ojs_lifespan(app):
            pass


@pytest.mark.asyncio
async def test_lifespan_reads_plugin_from_app_state() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    app.state.ojs_plugin = plugin

    async with ojs_lifespan(app) as state:
        assert state["ojs_client"] is mock_client


@pytest.mark.asyncio
async def test_lifespan_with_worker() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    mock_worker = AsyncMock()
    mock_worker.start = AsyncMock()
    mock_worker.stop = AsyncMock()
    plugin._worker = mock_worker

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin) as state:
        assert state["ojs_worker"] is mock_worker

    mock_worker.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_without_worker_yields_none() -> None:
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    _ojs_mock.Client = MagicMock(return_value=mock_client)

    app = FastAPI()
    async with ojs_lifespan(app, plugin=plugin) as state:
        assert state["ojs_worker"] is None
