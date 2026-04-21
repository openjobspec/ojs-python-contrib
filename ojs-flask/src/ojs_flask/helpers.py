"""Standalone helper functions for OJS within Flask request context."""

from __future__ import annotations

from typing import Any, cast

import ojs
from flask import current_app


def get_client() -> ojs.SyncClient:
    """Return the OJS client stored on the current Flask application.

    Raises:
        RuntimeError: If the OJS extension has not been initialized.
    """
    try:
        return cast(ojs.SyncClient, current_app.extensions["ojs"])
    except KeyError:
        raise RuntimeError(
            "OJS extension not initialized. Call OJS(app) or OJS.init_app(app) first."
        ) from None


def enqueue(job_type: str, args: list[Any] | None = None, **kwargs: Any) -> ojs.Job:
    """Enqueue a job using the OJS client from the current Flask app context.

    This is a shortcut for ``get_client().enqueue(...)``.

    Args:
        job_type: The job type identifier (e.g. ``"email.send"``).
        args: Positional arguments for the job handler.
        **kwargs: Additional keyword arguments forwarded to
            :meth:`ojs.SyncClient.enqueue` (``queue``, ``meta``, ``priority``, etc.).

    Returns:
        The enqueued :class:`ojs.Job`.
    """
    return get_client().enqueue(job_type, args, **kwargs)
