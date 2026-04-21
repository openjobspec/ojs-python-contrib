"""Transactional enqueue using SQLAlchemy session events.

Provides helpers that register after_commit event listeners to enqueue
OJS jobs only when the database transaction successfully commits.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Strong references to in-flight fire-and-forget enqueue tasks so the event
# loop does not garbage-collect them before they finish (see ruff RUF006).
_pending_tasks: set[asyncio.Task[None]] = set()


def _build_enqueue_kwargs(
    queue: str,
    priority: int,
    meta: dict[str, Any] | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    """Assemble enqueue keyword arguments, omitting ``meta`` when unset."""
    kwargs: dict[str, Any] = {"queue": queue, "priority": priority, **extra}
    if meta is not None:
        kwargs["meta"] = meta
    return kwargs


def enqueue_after_commit(
    session: Session,
    ojs_url: str,
    job_type: str,
    args: list[Any] | None = None,
    *,
    queue: str = "default",
    meta: dict[str, Any] | None = None,
    priority: int = 0,
    **kwargs: Any,
) -> None:
    """Register a job to be enqueued after the session commits.

    The job is only sent to OJS when the SQLAlchemy session successfully
    commits. If the session is rolled back, the job is never enqueued.

    Args:
        session: The SQLAlchemy session to attach the event to.
        ojs_url: Base URL of the OJS server (e.g., "http://localhost:8080").
        job_type: Dot-namespaced job type (e.g., "email.send").
        args: Positional arguments for the job handler.
        queue: Target queue name.
        meta: Extensible key-value metadata.
        priority: Job priority (higher = more important).
        **kwargs: Additional keyword arguments passed to ``ojs.SyncClient.enqueue``.
    """
    enqueue_args = args or []
    enqueue_kwargs = _build_enqueue_kwargs(queue, priority, meta, kwargs)

    def _after_commit(session: Session) -> None:
        import ojs

        try:
            with ojs.SyncClient(ojs_url) as client:
                client.enqueue(job_type, enqueue_args, **enqueue_kwargs)
            logger.info("Enqueued job %s after commit", job_type)
        except Exception:
            logger.exception("Failed to enqueue job %s after commit", job_type)

    event.listen(session, "after_commit", _after_commit, once=True)


def enqueue_after_commit_async(
    session: Session,
    ojs_url: str,
    job_type: str,
    args: list[Any] | None = None,
    *,
    queue: str = "default",
    meta: dict[str, Any] | None = None,
    priority: int = 0,
    **kwargs: Any,
) -> None:
    """Register a job to be enqueued asynchronously after the session commits.

    Uses the async OJS client to enqueue the job. The after_commit listener
    schedules an asyncio task on the running event loop.

    Args:
        session: The SQLAlchemy session to attach the event to.
        ojs_url: Base URL of the OJS server.
        job_type: Dot-namespaced job type.
        args: Positional arguments for the job handler.
        queue: Target queue name.
        meta: Extensible key-value metadata.
        priority: Job priority.
        **kwargs: Additional keyword arguments passed to ``ojs.Client.enqueue``.
    """
    enqueue_args = args or []
    enqueue_kwargs = _build_enqueue_kwargs(queue, priority, meta, kwargs)

    async def _do_enqueue() -> None:
        import ojs

        try:
            async with ojs.Client(ojs_url) as client:
                await client.enqueue(job_type, enqueue_args, **enqueue_kwargs)
            logger.info("Enqueued job %s after commit (async)", job_type)
        except Exception:
            logger.exception("Failed to enqueue job %s after commit (async)", job_type)

    def _after_commit(session: Session) -> None:
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_do_enqueue())
            _pending_tasks.add(task)
            task.add_done_callback(_pending_tasks.discard)
        except RuntimeError:
            asyncio.run(_do_enqueue())

    event.listen(session, "after_commit", _after_commit, once=True)
