"""Tests for OJS FastAPI event subscription helpers."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from ojs_fastapi.events import EventSubscription, OJSEventManager  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_event_handler() -> None:
    """@events.on should register a handler for the given event type."""
    manager = OJSEventManager()

    @manager.on("job.completed")
    async def on_completed(event: object) -> None:
        pass

    assert "job.completed" in manager.registered_events
    handlers = manager.get_handlers("job.completed")
    assert len(handlers) == 1
    assert handlers[0] is on_completed


def test_multiple_handlers_same_event() -> None:
    """Multiple handlers can be registered for the same event type."""
    manager = OJSEventManager()

    @manager.on("job.failed")
    async def handler_a(event: object) -> None:
        pass

    @manager.on("job.failed")
    async def handler_b(event: object) -> None:
        pass

    handlers = manager.get_handlers("job.failed")
    assert len(handlers) == 2
    assert handlers[0] is handler_a
    assert handlers[1] is handler_b


def test_registered_events() -> None:
    """registered_events should return all event types with handlers."""
    manager = OJSEventManager()

    @manager.on("job.completed")
    async def on_completed(event: object) -> None:
        pass

    @manager.on("job.failed")
    async def on_failed(event: object) -> None:
        pass

    assert sorted(manager.registered_events) == ["job.completed", "job.failed"]


def test_get_handlers() -> None:
    """get_handlers should return the list of handlers for an event type."""
    manager = OJSEventManager()

    @manager.on("job.completed")
    async def on_completed(event: object) -> None:
        pass

    assert len(manager.get_handlers("job.completed")) == 1


def test_get_handlers_unknown_returns_empty() -> None:
    """get_handlers should return an empty list for unregistered event types."""
    manager = OJSEventManager()
    assert manager.get_handlers("unknown.event") == []


@pytest.mark.asyncio
async def test_event_manager_start_stop() -> None:
    """start should create a listening task, stop should cancel it."""
    manager = OJSEventManager()

    @manager.on("job.completed")
    async def on_completed(event: object) -> None:
        pass

    mock_client = AsyncMock()
    # subscribe returns an async iterator that blocks forever
    mock_stream = AsyncMock()
    mock_stream.__aiter__ = MagicMock(return_value=mock_stream)
    mock_stream.__anext__ = AsyncMock(side_effect=asyncio.CancelledError)
    mock_client.subscribe = AsyncMock(return_value=mock_stream)

    await manager.start(mock_client)
    assert manager._task is not None
    assert not manager._task.done()

    await manager.stop()
    assert manager._task is None
