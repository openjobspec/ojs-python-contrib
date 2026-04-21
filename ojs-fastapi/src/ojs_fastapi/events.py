"""Server-Sent Events (SSE) subscription helpers for FastAPI + OJS."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EventSubscription:
    """Configuration for an OJS event subscription."""

    event_types: list[str] = field(default_factory=list)
    queues: list[str] = field(default_factory=list)
    callback: Callable[..., Coroutine[Any, Any, None]] | None = None


class OJSEventManager:
    """Manages OJS event subscriptions within a FastAPI application.

    Usage::

        events = OJSEventManager()

        @events.on("job.completed")
        async def on_completed(event):
            logger.info("Job %s completed", event.job_id)

        @events.on("job.failed")
        async def on_failed(event):
            await send_alert(event)
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = {}
        self._task: asyncio.Task[None] | None = None

    def on(self, event_type: str) -> Callable[..., Callable[..., Coroutine[Any, Any, None]]]:
        """Decorator to register an event handler for a specific event type."""

        def decorator(
            fn: Callable[..., Coroutine[Any, Any, None]],
        ) -> Callable[..., Coroutine[Any, Any, None]]:
            self._subscriptions.setdefault(event_type, []).append(fn)
            return fn

        return decorator

    @property
    def registered_events(self) -> list[str]:
        """Return list of event types with registered handlers."""
        return list(self._subscriptions.keys())

    def get_handlers(self, event_type: str) -> list[Callable[..., Coroutine[Any, Any, None]]]:
        """Return handlers registered for a given event type."""
        return self._subscriptions.get(event_type, [])

    async def start(self, client: Any) -> None:
        """Start listening for events from the OJS server."""

        async def _listen() -> None:
            try:
                async for event in await client.subscribe(list(self._subscriptions.keys())):
                    handlers = self._subscriptions.get(event.type, [])
                    for handler in handlers:
                        try:
                            await handler(event)
                        except Exception:
                            logger.exception("Event handler error for %s", event.type)
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Event subscription error")

        self._task = asyncio.create_task(_listen())

    async def stop(self) -> None:
        """Stop listening for events."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
