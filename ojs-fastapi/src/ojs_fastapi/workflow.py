"""Workflow helpers and dependency injection for FastAPI + OJS."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator

from fastapi import Request

if TYPE_CHECKING:
    import ojs


async def get_ojs_workflow(request: Request) -> AsyncIterator[ojs.Workflow]:
    """FastAPI dependency that yields a Workflow builder from the OJS client.

    Usage::

        @app.post("/pipelines")
        async def create_pipeline(wf: ojs.Workflow = Depends(get_ojs_workflow)):
            result = await wf.chain([
                {"type": "extract.data", "args": [source]},
                {"type": "transform.data", "args": []},
                {"type": "load.data", "args": [destination]},
            ])
            return {"workflow_id": result.id}
    """
    from ojs_fastapi.depends import OJSPlugin

    plugin: OJSPlugin = request.app.state.ojs_plugin
    client = plugin.client
    yield client.workflow()


class WorkflowBuilder:
    """High-level workflow builder for FastAPI applications.

    Provides convenience methods for common workflow patterns:
    chain, group, and batch.
    """

    def __init__(self, client: ojs.Client) -> None:
        self._client = client

    async def chain(self, steps: list[dict[str, Any]], *, queue: str = "default") -> Any:
        """Execute steps sequentially (pipeline pattern)."""
        import ojs

        return await self._client.workflow(ojs.chain(
            [ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue)) for s in steps]
        ))

    async def group(self, steps: list[dict[str, Any]], *, queue: str = "default") -> Any:
        """Execute steps in parallel (fan-out pattern)."""
        import ojs

        return await self._client.workflow(ojs.group(
            [ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue)) for s in steps]
        ))

    async def batch(self, steps: list[dict[str, Any]], *, callback: dict[str, Any] | None = None, queue: str = "default") -> Any:
        """Execute steps as a batch with optional completion callback."""
        import ojs

        jobs = [ojs.JobRequest(type=s["type"], args=s.get("args", []), queue=s.get("queue", queue)) for s in steps]
        cb = ojs.JobRequest(type=callback["type"], args=callback.get("args", []), queue=callback.get("queue", queue)) if callback else None
        return await self._client.workflow(ojs.batch(jobs, callback=cb))


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
