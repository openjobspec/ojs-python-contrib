"""Celery compatibility layer for Open Job Spec (OJS)."""

from __future__ import annotations

from typing import Any

from ojs_celery.adapter import OJSAdapter, OJSTask, ojs_task
from ojs_celery.compat import CeleryCompat

__all__ = [
    "CeleryCompat",
    "OJSAdapter",
    "OJSResultBackend",
    "OJSTask",
    "OJSTransport",
    "ojs_task",
]


def OJSResultBackend(*args: object, **kwargs: object) -> object:  # noqa: N802
    """Lazy import of OJSResultBackend to avoid requiring Celery at import time."""
    from ojs_celery.backend import OJSResultBackend as _Backend

    return _Backend(*args, **kwargs)


def OJSTransport(*args: object, **kwargs: object) -> object:  # noqa: N802
    """Lazy import of OJS Transport to avoid requiring Celery at import time."""
    from ojs_celery.transport import Transport as _Transport

    return _Transport(*args, **kwargs)


def migrate_task(
    celery_task: Any,
    adapter: OJSAdapter | None = None,
    ojs_url: str = "http://localhost:8080",
) -> OJSTask:
    """Lazy import of migrate_task to avoid requiring Celery at import time."""
    from ojs_celery.migration import migrate_task as _migrate_task

    return _migrate_task(celery_task, adapter, ojs_url)
