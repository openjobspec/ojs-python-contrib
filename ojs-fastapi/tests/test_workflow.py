"""Tests for OJS FastAPI workflow dependency injection."""

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

from ojs_fastapi.depends import OJSPlugin  # noqa: E402
from ojs_fastapi.workflow import (  # noqa: E402
    WorkflowBuilder,
    get_ojs_workflow,
    get_workflow_builder,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client() -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _build_app(plugin: OJSPlugin, mock_client: AsyncMock) -> FastAPI:
    app = FastAPI()
    plugin._client = mock_client
    app.state.ojs_plugin = plugin
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ojs_workflow_yields_workflow() -> None:
    """get_ojs_workflow should yield client.workflow() from app state."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()
    mock_workflow = MagicMock()
    mock_client.workflow = MagicMock(return_value=mock_workflow)

    app = _build_app(plugin, mock_client)

    @app.post("/pipelines")
    async def create_pipeline(wf: Any = Depends(get_ojs_workflow)) -> dict[str, str]:
        return {"workflow": str(type(wf).__name__)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/pipelines")
        assert resp.status_code == 200
        mock_client.workflow.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_builder_chain() -> None:
    """WorkflowBuilder.chain should call client.workflow with ojs.chain."""
    mock_client = AsyncMock()
    mock_result = MagicMock(id="wf-chain-1")
    mock_client.workflow = AsyncMock(return_value=mock_result)

    _ojs_mock.chain = MagicMock(return_value="chain_step")
    _ojs_mock.JobRequest = MagicMock(side_effect=lambda **kw: kw)

    builder = WorkflowBuilder(mock_client)
    result = await builder.chain([
        {"type": "extract.data", "args": ["src"]},
        {"type": "transform.data"},
    ])

    assert result.id == "wf-chain-1"
    _ojs_mock.chain.assert_called_once()
    mock_client.workflow.assert_awaited_once_with("chain_step")


@pytest.mark.asyncio
async def test_workflow_builder_group() -> None:
    """WorkflowBuilder.group should call client.workflow with ojs.group."""
    mock_client = AsyncMock()
    mock_result = MagicMock(id="wf-group-1")
    mock_client.workflow = AsyncMock(return_value=mock_result)

    _ojs_mock.group = MagicMock(return_value="group_step")
    _ojs_mock.JobRequest = MagicMock(side_effect=lambda **kw: kw)

    builder = WorkflowBuilder(mock_client)
    result = await builder.group([
        {"type": "resize.image", "args": ["img1"]},
        {"type": "resize.image", "args": ["img2"]},
    ])

    assert result.id == "wf-group-1"
    _ojs_mock.group.assert_called_once()
    mock_client.workflow.assert_awaited_once_with("group_step")


@pytest.mark.asyncio
async def test_workflow_builder_batch() -> None:
    """WorkflowBuilder.batch should call client.workflow with ojs.batch."""
    mock_client = AsyncMock()
    mock_result = MagicMock(id="wf-batch-1")
    mock_client.workflow = AsyncMock(return_value=mock_result)

    _ojs_mock.batch = MagicMock(return_value="batch_step")
    _ojs_mock.JobRequest = MagicMock(side_effect=lambda **kw: kw)

    builder = WorkflowBuilder(mock_client)
    result = await builder.batch(
        [{"type": "process.item", "args": [1]}, {"type": "process.item", "args": [2]}],
        callback={"type": "batch.done", "args": []},
    )

    assert result.id == "wf-batch-1"
    _ojs_mock.batch.assert_called_once()
    mock_client.workflow.assert_awaited_once_with("batch_step")


@pytest.mark.asyncio
async def test_get_workflow_builder_dependency() -> None:
    """get_workflow_builder should yield a WorkflowBuilder from app state."""
    plugin = OJSPlugin(url="http://localhost:8080")
    mock_client = _make_mock_client()

    app = _build_app(plugin, mock_client)

    @app.post("/build")
    async def build_wf(builder: WorkflowBuilder = Depends(get_workflow_builder)) -> dict[str, str]:
        return {"type": type(builder).__name__}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/build")
        assert resp.status_code == 200
        assert resp.json()["type"] == "WorkflowBuilder"
