"""Job handler decorator and registry for ojs_django."""

from __future__ import annotations

import functools
from collections.abc import Callable, Coroutine
from typing import Any, Generic, TypeVar

import ojs

from ojs_django.conf import get_ojs_settings

T = TypeVar("T")

# Module-level registry: job_type -> handler function
_registry: dict[str, OJSJobWrapper[Any]] = {}


class OJSJobWrapper(Generic[T]):
    """Wrapper around a job handler with enqueue capabilities.

    Created by the ``@ojs_job`` decorator. The wrapped function can be
    called directly (for use as a handler) or via ``.enqueue()`` /
    ``.enqueue_after_commit()`` to submit a job to the OJS server.
    """

    def __init__(
        self,
        fn: Callable[[ojs.JobContext], Coroutine[Any, Any, T]],
        job_type: str,
        *,
        queue: str | None = None,
        retry: ojs.RetryPolicy | None = None,
        priority: int = 0,
        tags: list[str] | None = None,
    ) -> None:
        self.fn = fn
        self.job_type = job_type
        self.queue = queue
        self.retry = retry
        self.priority = priority
        self.tags = tags
        functools.update_wrapper(self, fn)

    async def __call__(self, ctx: ojs.JobContext) -> T:
        """Call the underlying handler function."""
        return await self.fn(ctx)

    def enqueue(self, *args: Any, **kwargs: Any) -> ojs.Job:
        """Enqueue this job type with the given arguments.

        Keyword arguments override the decorator defaults for ``queue``,
        ``meta``, ``priority``, ``retry``, and ``tags``.

        Usage::

            @ojs_job("email.send", queue="emails")
            async def send_email(ctx):
                ...

            send_email.enqueue("user@test.com", "welcome")
        """
        from ojs_django.backend import enqueue as _enqueue

        queue = kwargs.pop("queue", self.queue)
        meta = kwargs.pop("meta", None)
        priority = kwargs.pop("priority", self.priority)
        retry = kwargs.pop("retry", self.retry)
        tags = kwargs.pop("tags", self.tags)

        return _enqueue(
            self.job_type,
            *args,
            queue=queue,
            meta=meta,
            priority=priority,
            retry=retry,
            tags=tags,
            **kwargs,
        )

    def enqueue_after_commit(
        self,
        *args: Any,
        using: str = "default",
        **kwargs: Any,
    ) -> None:
        """Enqueue this job type after the current transaction commits.

        Usage::

            with transaction.atomic():
                user = User.objects.create(...)
                send_email.enqueue_after_commit(user.email, "welcome")
        """
        from ojs_django.backend import enqueue_after_commit as _enqueue_after_commit

        cfg = get_ojs_settings()
        queue = kwargs.pop("queue", self.queue or cfg.default_queue)
        meta = kwargs.pop("meta", None)

        _enqueue_after_commit(
            self.job_type,
            list(args),
            queue=queue,
            meta=meta,
            using=using,
            **kwargs,
        )


def ojs_job(
    job_type: str,
    *,
    queue: str | None = None,
    retry: ojs.RetryPolicy | None = None,
    priority: int = 0,
    tags: list[str] | None = None,
) -> Callable[
    [Callable[[ojs.JobContext], Coroutine[Any, Any, Any]]],
    OJSJobWrapper[Any],
]:
    """Register a function as a handler for an OJS job type.

    Usage::

        @ojs_job("email.send", queue="emails", retry=RetryPolicy(max_attempts=3))
        async def handle_email(ctx: ojs.JobContext) -> None:
            to = ctx.args[0]
            await send_email(to)

        # Enqueue programmatically
        handle_email.enqueue("user@test.com", "welcome")

    Args:
        job_type: Dot-namespaced job type (e.g., ``"email.send"``).
        queue: Default queue for this job type.
        retry: Default retry policy for this job type.
        priority: Default priority for this job type.
        tags: Default tags for this job type.
    """

    def decorator(
        fn: Callable[[ojs.JobContext], Coroutine[Any, Any, Any]],
    ) -> OJSJobWrapper[Any]:
        if job_type in _registry:
            raise ValueError(
                f"Duplicate handler for job type {job_type!r}: "
                f"{_registry[job_type].fn.__name__} and {fn.__name__}"
            )
        wrapper = OJSJobWrapper(
            fn,
            job_type,
            queue=queue,
            retry=retry,
            priority=priority,
            tags=tags,
        )
        _registry[job_type] = wrapper
        return wrapper

    return decorator


def get_registry() -> dict[str, OJSJobWrapper[Any]]:
    """Return the current handler registry."""
    return _registry
