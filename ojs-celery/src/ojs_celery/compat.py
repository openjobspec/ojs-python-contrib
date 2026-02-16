"""Celery-app-compatible interface backed by OJS.

Provides a ``CeleryCompat`` class that acts as a drop-in replacement for a
Celery application object, supporting ``@app.task()`` and ``app.send_task()``.

No Celery installation is required to use this module.
"""

from __future__ import annotations

import datetime
from typing import Any, Callable

import ojs

from ojs_celery.adapter import OJSTask


class CeleryCompat:
    """A Celery-app-like interface backed by OJS.

    Supports the most common Celery app patterns:

    - ``@app.task(name=...)`` decorator
    - ``app.send_task(name, args=...)`` for dynamic dispatch
    - Concept mapping from Celery to OJS
    """

    def __init__(
        self,
        ojs_url: str = "http://localhost:8080",
        *,
        default_queue: str = "default",
    ) -> None:
        self.ojs_url = ojs_url
        self.default_queue = default_queue
        self._client: ojs.SyncClient | None = None
        self._tasks: dict[str, OJSTask] = {}

    @property
    def client(self) -> ojs.SyncClient:
        """Lazy-initialized OJS SyncClient."""
        if self._client is None:
            self._client = ojs.SyncClient(self.ojs_url)
        return self._client

    @property
    def tasks(self) -> dict[str, OJSTask]:
        """Registry of all registered tasks."""
        return dict(self._tasks)

    def task(
        self,
        fn: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        bind: bool = False,
        max_retries: int | None = None,
        queue: str | None = None,
        **_kwargs: Any,
    ) -> Any:
        """Register a function as a task (Celery-compatible decorator).

        Args:
            fn: The function to decorate (when used without parentheses).
            name: Task name. Defaults to the function's qualified name.
            bind: Accepted for Celery compatibility (ignored).
            max_retries: Accepted for Celery compatibility (stored in meta).
            queue: Default queue for this task.
        """

        def decorator(func: Callable[..., Any]) -> OJSTask:
            task_name = name or f"{func.__module__}.{func.__qualname__}"
            task_obj = _CompatTask(
                name=task_name,
                fn=func,
                _adapter_compat=self,
                _default_queue=queue or self.default_queue,
                _max_retries=max_retries,
            )
            self._tasks[task_name] = task_obj
            return task_obj

        if fn is not None:
            return decorator(fn)
        return decorator

    def send_task(
        self,
        name: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        queue: str | None = None,
        countdown: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ojs.Job:
        """Dynamically dispatch a task by name (Celery-compatible).

        Args:
            name: The task name to enqueue.
            args: Positional arguments for the job.
            kwargs: Keyword arguments — stored in meta under ``kwargs``.
            queue: Target queue (defaults to ``default_queue``).
            countdown: Delay in seconds before the job becomes available.
            meta: Arbitrary metadata attached to the job.
        """
        job_args = list(args) if args else []
        job_meta: dict[str, Any] = dict(meta) if meta else {}
        if kwargs:
            job_meta["kwargs"] = kwargs

        enqueue_kwargs: dict[str, Any] = {
            "queue": queue or self.default_queue,
        }
        if job_meta:
            enqueue_kwargs["meta"] = job_meta
        if countdown is not None:
            delay_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                seconds=countdown
            )
            enqueue_kwargs["delay_until"] = delay_until.isoformat()

        return self.client.enqueue(name, job_args, **enqueue_kwargs)

    def close(self) -> None:
        """Close the underlying OJS client."""
        if self._client is not None:
            self._client.close()
            self._client = None


class _CompatTask(OJSTask):
    """Extended OJSTask with CeleryCompat-specific defaults."""

    def __init__(
        self,
        name: str,
        fn: Callable[..., Any],
        _adapter_compat: CeleryCompat,
        _default_queue: str = "default",
        _max_retries: int | None = None,
    ) -> None:
        # Store compat-specific attributes before calling parent
        self._compat = _adapter_compat
        self._default_queue = _default_queue
        self._max_retries = _max_retries
        # OJSTask uses _adapter for enqueue; we need a shim
        super().__init__(name=name, fn=fn, _adapter=None)  # type: ignore[arg-type]

    def delay(self, *args: Any) -> ojs.Job:
        """Enqueue with default queue."""
        return self.apply_async(args=list(args))

    def apply_async(
        self,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        queue: str | None = None,
        countdown: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ojs.Job:
        """Enqueue with compat defaults."""
        return self._compat.send_task(
            self.name,
            args=args,
            kwargs=kwargs,
            queue=queue or self._default_queue,
            countdown=countdown,
            meta=meta,
        )
