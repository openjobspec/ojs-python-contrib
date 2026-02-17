"""Job handler decorator and registry for ojs_django."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import ojs

# Module-level registry: job_type -> handler function
_registry: dict[str, Callable[[ojs.JobContext], Coroutine[Any, Any, Any]]] = {}


def ojs_job(
    job_type: str,
) -> Callable[
    [Callable[[ojs.JobContext], Coroutine[Any, Any, Any]]],
    Callable[[ojs.JobContext], Coroutine[Any, Any, Any]],
]:
    """Register a function as a handler for an OJS job type.

    Usage::

        @ojs_job("email.send")
        async def handle_email(ctx: ojs.JobContext) -> None:
            to = ctx.args[0]
            await send_email(to)
    """

    def decorator(
        fn: Callable[[ojs.JobContext], Coroutine[Any, Any, Any]],
    ) -> Callable[[ojs.JobContext], Coroutine[Any, Any, Any]]:
        if job_type in _registry:
            raise ValueError(
                f"Duplicate handler for job type {job_type!r}: "
                f"{_registry[job_type].__name__} and {fn.__name__}"
            )
        _registry[job_type] = fn
        return fn

    return decorator


def get_registry() -> dict[str, Callable[[ojs.JobContext], Coroutine[Any, Any, Any]]]:
    """Return the current handler registry."""
    return _registry
