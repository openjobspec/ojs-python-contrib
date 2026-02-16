"""Celery compatibility layer for Open Job Spec (OJS)."""

from __future__ import annotations

from ojs_celery.adapter import OJSAdapter, OJSTask, ojs_task
from ojs_celery.compat import CeleryCompat

__all__ = [
    "CeleryCompat",
    "OJSAdapter",
    "OJSTask",
    "ojs_task",
]


def migrate_task(*args: object, **kwargs: object) -> object:
    """Lazy import of migrate_task to avoid requiring Celery at import time."""
    from ojs_celery.migration import migrate_task as _migrate_task

    return _migrate_task(*args, **kwargs)
