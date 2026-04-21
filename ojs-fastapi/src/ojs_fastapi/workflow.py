"""Workflow helpers and dependency injection for FastAPI + OJS."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import Request

if TYPE_CHECKING:
    import ojs


async def get_ojs_workflow(request: Request) -> AsyncIterator[WorkflowBuilder]:
    """FastAPI dependency that yields a :class:`WorkflowBuilder` for the request.

    Usage::

        @app.post("/pipelines")
        async def create_pipeline(wf: WorkflowBuilder = Depends(get_ojs_workflow)):
            result = await wf.chain([
                {"type": "extract.data", "args": [source]},
                {"type": "transform.data", "args": []},
                {"type": "load.data", "args": [destination]},
            ])
            return {"workflow_id": result.id}
    """
    from ojs_fastapi.depends import OJSPlugin

    plugin: OJSPlugin = request.app.state.ojs_plugin
    yield WorkflowBuilder(plugin.client)


class WorkflowBuilder:
    """High-level workflow builder for FastAPI applications.

    Provides convenience methods for common workflow patterns:
    chain, group, and batch.
    """

    def __init__(self, client: ojs.Client) -> None:
        self._client = client

    async def chain(
        self, steps: list[dict[str, Any]], *, name: str = "chain", queue: str = "default"
    ) -> Any:
        """Execute steps sequentially (pipeline pattern)."""
        import ojs

        jobs = [
            ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue))
            for s in steps
        ]
        return await self._client.workflow(ojs.chain(name, jobs))

    async def group(
        self, steps: list[dict[str, Any]], *, name: str = "group", queue: str = "default"
    ) -> Any:
        """Execute steps in parallel (fan-out pattern)."""
        import ojs

        jobs = [
            ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue))
            for s in steps
        ]
        return await self._client.workflow(ojs.group(name, jobs))

    async def batch(
        self,
        steps: list[dict[str, Any]],
        *,
        callback: dict[str, Any] | None = None,
        name: str = "batch",
        queue: str = "default",
    ) -> Any:
        """Execute steps as a batch with an optional completion callback."""
        import ojs

        jobs = [
            ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue))
            for s in steps
        ]
        on_complete = (
            ojs.JobRequest(
                type=callback["type"],
                args=callback.get("args", []),
                queue=callback.get("queue", queue),
            )
            if callback
            else None
        )
        return await self._client.workflow(ojs.batch(name, jobs, on_complete=on_complete))


async def get_workflow_builder(request: Request) -> AsyncIterator[WorkflowBuilder]:
    """FastAPI dependency that yields a WorkflowBuilder.

    Usage::

        @app.post("/pipelines/etl")
        async def etl(builder: WorkflowBuilder = Depends(get_workflow_builder)):
            return await builder.chain([...])
    """
    from ojs_fastapi.depends import OJSPlugin

    plugin: OJSPlugin = request.app.state.ojs_plugin
    yield WorkflowBuilder(plugin.client)
