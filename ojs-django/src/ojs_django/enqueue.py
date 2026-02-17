"""Job enqueue helpers with Django transaction awareness."""

from __future__ import annotations

import functools
from typing import Any

import ojs
from django.db import transaction

from ojs_django.settings import get_ojs_settings

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


def enqueue(
    job_type: str,
    args: list[Any] | None = None,
    *,
    queue: str = "default",
    meta: dict[str, Any] | None = None,
    **kwargs: Any,
) -> ojs.Job:
    """Enqueue a job immediately (outside any transaction context).

    This is a thin wrapper around :meth:`ojs.SyncClient.enqueue`.
    """
    return get_client().enqueue(job_type, args, queue=queue, meta=meta, **kwargs)


def enqueue_after_commit(
    job_type: str,
    args: list[Any] | None = None,
    *,
    queue: str = "default",
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
        **kwargs: Additional keyword arguments forwarded to
            :meth:`ojs.SyncClient.enqueue`.
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
    queue: str,
    meta: dict[str, Any] | None,
    **kwargs: Any,
) -> None:
    """Internal helper executed by ``on_commit``."""
    get_client().enqueue(job_type, args, queue=queue, meta=meta, **kwargs)
