"""OJS adapter with Celery-compatible task API."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import ojs


def _countdown_to_delay_until(countdown: float) -> str:
    """Convert a Celery countdown (seconds from now) to an ISO 8601 timestamp."""
    delay_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=countdown)
    return delay_until.isoformat()


@dataclass
class OJSTask:
    """A task object that mimics Celery's task interface.

    Provides `.delay()` and `.apply_async()` methods that enqueue jobs
    via the OJS SyncClient.
    """

    name: str
    fn: Callable[..., Any]
    _adapter: OJSAdapter

    def delay(self, *args: Any) -> ojs.Job:
        """Enqueue this task with positional arguments (Celery-compatible)."""
        return self._adapter.enqueue(self.name, list(args))

    def apply_async(
        self,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        queue: str | None = None,
        countdown: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ojs.Job:
        """Enqueue this task with full options (Celery-compatible).

        Args:
            args: Positional arguments for the job.
            kwargs: Keyword arguments — merged into meta under the ``kwargs`` key.
            queue: Target queue name.
            countdown: Delay in seconds before the job becomes available.
            meta: Arbitrary metadata attached to the job.
        """
        job_args = list(args) if args else []

        job_meta: dict[str, Any] = dict(meta) if meta else {}
        if kwargs:
            job_meta["kwargs"] = kwargs

        enqueue_kwargs: dict[str, Any] = {}
        if queue is not None:
            enqueue_kwargs["queue"] = queue
        if job_meta:
            enqueue_kwargs["meta"] = job_meta
        if countdown is not None:
            enqueue_kwargs["delay_until"] = _countdown_to_delay_until(countdown)

        return self._adapter.enqueue(self.name, job_args, **enqueue_kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Call the underlying function directly (local execution)."""
        return self.fn(*args, **kwargs)


@dataclass
class OJSAdapter:
    """Celery-compatible adapter backed by OJS.

    Provides a `@task()` decorator that returns :class:`OJSTask` objects
    with `.delay()` and `.apply_async()` methods.
    """

    ojs_url: str
    _client: ojs.SyncClient | None = field(default=None, init=False, repr=False)
    _tasks: dict[str, OJSTask] = field(default_factory=dict, init=False, repr=False)

    @property
    def client(self) -> ojs.SyncClient:
        """Lazy-initialized OJS SyncClient."""
        if self._client is None:
            self._client = ojs.SyncClient(self.ojs_url)
        return self._client

    @property
    def tasks(self) -> dict[str, OJSTask]:
        """Registry of all tasks registered with this adapter."""
        return dict(self._tasks)

    def task(
        self,
        name: str | None = None,
        **_kwargs: Any,
    ) -> Callable[[Callable[..., Any]], OJSTask]:
        """Decorator to register a function as an OJS task.

        Args:
            name: Task name. Defaults to the function's qualified name.
        """

        def decorator(fn: Callable[..., Any]) -> OJSTask:
            task_name = name or f"{fn.__module__}.{fn.__qualname__}"
            ojs_task_obj = OJSTask(name=task_name, fn=fn, _adapter=self)
            self._tasks[task_name] = ojs_task_obj
            return ojs_task_obj

        return decorator

    def enqueue(self, job_type: str, args: list[Any], **kwargs: Any) -> ojs.Job:
        """Enqueue a job via the OJS SyncClient."""
        return self.client.enqueue(job_type, args, **kwargs)

    def close(self) -> None:
        """Close the underlying OJS client."""
        if self._client is not None:
            self._client.close()
            self._client = None


# Module-level adapter for simple usage
_default_adapter: OJSAdapter | None = None


def ojs_task(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    ojs_url: str = "http://localhost:8080",
) -> Any:
    """Module-level decorator for quick task registration.

    Usage::

        @ojs_task(name="email.send", ojs_url="http://localhost:8080")
        def send_email(to: str, body: str):
            ...

        send_email.delay("user@example.com", "Hello!")
    """
    global _default_adapter

    if _default_adapter is None or _default_adapter.ojs_url != ojs_url:
        _default_adapter = OJSAdapter(ojs_url=ojs_url)

    def decorator(func: Callable[..., Any]) -> OJSTask:
        task_name = name or f"{func.__module__}.{func.__qualname__}"
        return _default_adapter.task(name=task_name)(func)

    if fn is not None:
        return decorator(fn)
    return decorator
