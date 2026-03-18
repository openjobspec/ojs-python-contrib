"""Health check router for FastAPI + OJS."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response model for the OJS health check endpoint."""

    status: str = Field(..., description="'healthy' or 'unhealthy'")
    ojs_url: str = Field(..., description="OJS server URL")
    queues: list[dict[str, Any]] = Field(default_factory=list)
    worker_running: bool = Field(default=False)
    error: str | None = Field(default=None)


class QueueStatusResponse(BaseModel):
    """Response model for individual queue status."""

    name: str
    size: int = 0
    pending: int = 0
    active: int = 0


def create_health_router(prefix: str = "/ojs", tags: list[str] | None = None) -> APIRouter:
    """Create an APIRouter with OJS health and status endpoints.

    Args:
        prefix: URL prefix for the router.
        tags: OpenAPI tags.

    Returns:
        FastAPI APIRouter with /health and /status endpoints.
    """
    router = APIRouter(prefix=prefix, tags=tags or ["ojs"])

    @router.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        """Health check: verifies OJS connectivity and reports worker status."""
        from ojs_fastapi.depends import OJSPlugin

        plugin: OJSPlugin = request.app.state.ojs_plugin
        try:
            client = plugin.client
            queues = await client.list_queues()
            return HealthResponse(
                status="healthy",
                ojs_url=plugin.url,
                queues=[{"name": q.name} for q in queues] if queues else [],
                worker_running=plugin.worker is not None,
            )
        except Exception as exc:
            return HealthResponse(
                status="unhealthy",
                ojs_url=plugin.url,
                error=str(exc),
            )

    @router.get("/status")
    async def status(request: Request) -> dict[str, Any]:
        """Detailed OJS status with queue statistics and worker info."""
        from ojs_fastapi.depends import OJSPlugin

        plugin: OJSPlugin = request.app.state.ojs_plugin
        client = plugin.client
        queues = await client.list_queues()
        queue_stats = []
        for q in (queues or []):
            try:
                stats = await client.queue_stats(q.name)
                queue_stats.append({"name": q.name, "stats": stats})
            except Exception:
                queue_stats.append({"name": q.name, "stats": None})

        return {
            "ojs_url": plugin.url,
            "worker_running": plugin.worker is not None,
            "configured_queues": plugin.queues,
            "concurrency": plugin.concurrency,
            "queues": queue_stats,
        }

    return router
