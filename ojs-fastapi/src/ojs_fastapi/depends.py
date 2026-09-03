"""FastAPI dependency injection for OJS."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from fastapi import Request

if TYPE_CHECKING:
    import ojs


@dataclass
class OJSPlugin:
    """Configuration and lifecycle manager for OJS within a FastAPI application.

    Stores the OJS server URL, queue configuration, and worker settings.
    The plugin manages the ``ojs.Client`` and optional ``ojs.Worker`` instances,
    storing them on ``app.state`` so they can be injected via FastAPI dependencies.
    """

    url: str
    queues: list[str] = field(default_factory=lambda: ["default"])
    concurrency: int = 10
    poll_interval: float = 2.0

    _client: Any = field(default=None, init=False, repr=False)
    _worker: Any = field(default=None, init=False, repr=False)

    @property
    def client(self) -> ojs.Client:
        """Return the managed client, raising if not yet started."""
        if self._client is None:
            raise RuntimeError(
                "OJS client has not been started. Use ojs_lifespan or start manually."
            )
        return cast("ojs.Client", self._client)

    @property
    def worker(self) -> ojs.Worker | None:
        """Return the managed worker, or ``None`` if not configured."""
        return cast("ojs.Worker | None", self._worker)


async def get_ojs_client(request: Request) -> AsyncIterator[ojs.Client]:
    """FastAPI dependency that yields the OJS client from application state.

    Usage::

        @app.post("/jobs")
        async def create_job(client: ojs.Client = Depends(get_ojs_client)):
            job = await client.enqueue("email.send", ["user@example.com"])
            return {"job_id": job.id}
    """
    plugin: OJSPlugin = request.app.state.ojs_plugin
    yield plugin.client
