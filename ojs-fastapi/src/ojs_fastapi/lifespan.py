"""Lifespan context manager for OJS client and worker startup/shutdown."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from ojs_fastapi.depends import OJSPlugin


@asynccontextmanager
async def ojs_lifespan(
    app: FastAPI,
    plugin: OJSPlugin | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Async context manager that manages OJS client and worker lifecycle.

    Use as the FastAPI ``lifespan`` parameter::

        plugin = OJSPlugin(url="http://localhost:8080", queues=["default", "emails"])

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with ojs_lifespan(app, plugin=plugin) as state:
                yield state

        app = FastAPI(lifespan=lifespan)

    On startup the client is opened, an optional worker is started in a background
    task, and both are torn down cleanly on shutdown.
    """
    import ojs

    if plugin is None:
        plugin = getattr(app.state, "ojs_plugin", None)
        if plugin is None:
            raise RuntimeError(
                "No OJSPlugin provided. Pass it to ojs_lifespan() or set app.state.ojs_plugin."
            )

    # Store the plugin on app state for dependency injection
    app.state.ojs_plugin = plugin

    # Create and open the client
    client = ojs.Client(plugin.url)
    plugin._client = client

    worker_task: asyncio.Task[None] | None = None

    async with client:
        # Start worker if handlers have been registered
        if plugin._worker is not None:
            worker = plugin._worker

            async def _run_worker() -> None:
                with contextlib.suppress(asyncio.CancelledError):
                    await worker.start()

            worker_task = asyncio.create_task(_run_worker())

        try:
            yield {"ojs_client": client, "ojs_worker": plugin._worker}
        finally:
            # Shutdown worker
            if plugin._worker is not None:
                await plugin._worker.stop()
            if worker_task is not None:
                worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker_task

            plugin._client = None
