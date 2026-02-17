"""Django job backend — the primary enqueue API.

Provides ``enqueue``, ``enqueue_at``, ``enqueue_batch`` with
``transaction.on_commit`` support for transactional safety.
"""

from __future__ import annotations

import functools
from datetime import datetime, timezone
from typing import Any

import ojs
from django.db import transaction

from ojs_django.conf import get_ojs_settings

# Lazy-initialised shared client (created once per process)
_sync_client: ojs.SyncClient | None = None


def get_client() -> ojs.SyncClient:
    """Return a process-wide :class:`ojs.SyncClient`.

    The client is lazily created on first call and reused afterward.
    """
    global _sync_client  # noqa: PLW0603
    if _sync_client is None:
        cfg = get_ojs_settings()
        _sync_client = ojs.SyncClient(cfg.url)
    return _sync_client


def reset_client() -> None:
    """Reset the cached client. Useful for testing."""
    global _sync_client  # noqa: PLW0603
    if _sync_client is not None:
        _sync_client.close()
    _sync_client = None


def enqueue(
    job_type: str,
    *args: Any,
    queue: str | None = None,
    meta: dict[str, Any] | None = None,
    priority: int = 0,
    retry: ojs.RetryPolicy | None = None,
    tags: list[str] | None = None,
    **options: Any,
) -> ojs.Job:
    """Enqueue a job immediately (outside any transaction context).

    Args:
        job_type: Dot-namespaced job type (e.g., ``"email.send"``).
        *args: Positional arguments for the job handler (JSON-serializable).
        queue: Target queue name. If None, uses the configured default.
        meta: Extensible key-value metadata.
        priority: Job priority (higher = more important).
        retry: Retry policy override.
        tags: Tags for filtering and observability.
        **options: Additional keyword arguments forwarded to the SDK client.

    Returns:
        The created Job with server-assigned ID and state.
    """
    cfg = get_ojs_settings()
    resolved_queue = cfg.prefixed_queue(queue or cfg.default_queue)
    return get_client().enqueue(
        job_type,
        list(args),
        queue=resolved_queue,
        meta=meta,
        priority=priority,
        retry=retry,
        tags=tags,
        **options,
    )


def enqueue_at(
    job_type: str,
    scheduled_at: datetime | str,
    *args: Any,
    queue: str | None = None,
    meta: dict[str, Any] | None = None,
    **options: Any,
) -> ojs.Job:
    """Enqueue a job to run at a specific time.

    Args:
        job_type: Dot-namespaced job type.
        scheduled_at: When the job should run. A datetime or ISO 8601 string.
        *args: Positional arguments for the job handler.
        queue: Target queue name. If None, uses the configured default.
        meta: Extensible key-value metadata.
        **options: Additional keyword arguments forwarded to the SDK client.

    Returns:
        The created Job with server-assigned ID and state.
    """
    cfg = get_ojs_settings()
    resolved_queue = cfg.prefixed_queue(queue or cfg.default_queue)

    if isinstance(scheduled_at, datetime):
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        delay_until = scheduled_at.isoformat()
    else:
        delay_until = scheduled_at

    return get_client().enqueue(
        job_type,
        list(args),
        queue=resolved_queue,
        meta=meta,
        delay_until=delay_until,
        **options,
    )


def enqueue_batch(
    jobs: list[dict[str, Any]],
) -> list[ojs.Job]:
    """Enqueue multiple jobs in a single atomic operation.

    Args:
        jobs: List of job dicts, each with ``type``, ``args``, and optional
              ``queue``, ``meta``, ``priority``, ``retry``, ``tags``.

    Returns:
        List of created Jobs.

    Example::

        enqueue_batch([
            {"type": "email.send", "args": ["a@b.com", "welcome"]},
            {"type": "email.send", "args": ["c@d.com", "welcome"], "queue": "bulk"},
        ])
    """
    cfg = get_ojs_settings()
    requests: list[ojs.JobRequest] = []
    for job_dict in jobs:
        queue = cfg.prefixed_queue(job_dict.get("queue", cfg.default_queue))
        retry = None
        if "retry" in job_dict:
            retry = (
                job_dict["retry"]
                if isinstance(job_dict["retry"], ojs.RetryPolicy)
                else ojs.RetryPolicy(**job_dict["retry"])
            )
        requests.append(
            ojs.JobRequest(
                type=job_dict["type"],
                args=job_dict.get("args", []),
                queue=queue,
                meta=job_dict.get("meta"),
                priority=job_dict.get("priority", 0),
                retry=retry,
                tags=job_dict.get("tags"),
            )
        )
    return get_client().enqueue_batch(requests)


def enqueue_after_commit(
    job_type: str,
    args: list[Any] | None = None,
    *,
    queue: str | None = None,
    meta: dict[str, Any] | None = None,
    using: str = "default",
    **kwargs: Any,
) -> None:
    """Enqueue a job only after the current database transaction commits.

    Uses :func:`django.db.transaction.on_commit` so the job is never
    sent to the OJS server if the surrounding transaction rolls back.

    Args:
        job_type: Dot-namespaced job type (e.g., ``"email.send"``).
        args: Positional arguments for the job handler.
        queue: Target queue name.
        meta: Extensible key-value metadata.
        using: Database alias for the transaction (default: ``"default"``).
        **kwargs: Additional keyword arguments forwarded to the SDK client.
    """
    callback = functools.partial(
        _do_enqueue,
        job_type=job_type,
        args=args,
        queue=queue,
        meta=meta,
        **kwargs,
    )
    transaction.on_commit(callback, using=using)


def _do_enqueue(
    *,
    job_type: str,
    args: list[Any] | None,
    queue: str | None,
    meta: dict[str, Any] | None,
    **kwargs: Any,
) -> None:
    """Internal helper executed by ``on_commit``."""
    cfg = get_ojs_settings()
    resolved_queue = cfg.prefixed_queue(queue or cfg.default_queue)
    get_client().enqueue(job_type, args, queue=resolved_queue, meta=meta, **kwargs)
