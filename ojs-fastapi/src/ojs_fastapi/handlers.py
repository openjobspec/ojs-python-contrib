"""Job handler registration and worker lifecycle for FastAPI + OJS."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from ojs_fastapi.depends import OJSPlugin


@dataclass
class JobHandler:
    """Metadata for a registered job handler."""

    type: str
    handler: Callable[..., Coroutine[Any, Any, None]]
    queue: str | None = None
    concurrency: int | None = None


class OJSHandlerRegistry:
    """Registry for OJS job handlers, integrated with FastAPI.

    Usage::

        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx):
            to = ctx.args[0]
            await send_mail(to)

        @registry.handler("report.generate", queue="reports")
        async def generate_report(ctx):
            report_id = ctx.args[0]
            await build_report(report_id)

        # Attach to plugin before lifespan
        registry.attach(plugin)
    """

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler] = {}

    def handler(
        self,
        job_type: str,
        *,
        queue: str | None = None,
        concurrency: int | None = None,
    ) -> Callable[..., Callable[..., Coroutine[Any, Any, None]]]:
        """Decorator to register a job handler for a given type.

        Args:
            job_type: The OJS job type string.
            queue: Optional queue to process from.
            concurrency: Optional per-handler concurrency.

        Returns:
            Decorator that registers the function as a handler.
        """

        def decorator(
            fn: Callable[..., Coroutine[Any, Any, None]],
        ) -> Callable[..., Coroutine[Any, Any, None]]:
            self._handlers[job_type] = JobHandler(
                type=job_type,
                handler=fn,
                queue=queue,
                concurrency=concurrency,
            )
            return fn

        return decorator

    def attach(self, plugin: OJSPlugin) -> None:
        """Attach all registered handlers to an OJSPlugin.

        This configures the plugin's worker with all registered handlers.
        Call this before the FastAPI lifespan starts.
        """
        import ojs

        worker = ojs.Worker(
            url=plugin.url,
            queues=plugin.queues,
            concurrency=plugin.concurrency,
            poll_interval=plugin.poll_interval,
        )

        for job_type, jh in self._handlers.items():
            worker.handler(job_type, jh.handler)

        plugin._worker = worker

    @property
    def registered_types(self) -> list[str]:
        """Return list of registered job type names."""
        return list(self._handlers.keys())

    def get_handler(self, job_type: str) -> JobHandler | None:
        """Return handler metadata for a given job type."""
        return self._handlers.get(job_type)


def ojs_handler(
    job_type: str,
    *,
    queue: str | None = None,
) -> Callable[..., Callable[..., Coroutine[Any, Any, None]]]:
    """Standalone decorator for marking functions as OJS handlers.

    Use with manual registration or auto-discovery patterns::

        @ojs_handler("email.send")
        async def send_email(ctx):
            ...

    The decorated function gains an ``_ojs_handler`` attribute with metadata.
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, None]],
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        fn._ojs_handler = JobHandler(  # type: ignore[attr-defined]
            type=job_type,
            handler=fn,
            queue=queue,
        )
        return fn

    return decorator
