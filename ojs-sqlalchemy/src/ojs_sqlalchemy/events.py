"""Event listener system for OJS job state change notifications.

Allows registering callbacks that fire when OJS jobs transition between states.
Uses SQLAlchemy's event system and the OJS outbox table to track state changes.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import event

from .models import OJSOutboxEntry

logger = logging.getLogger(__name__)


@dataclass
class JobStateEvent:
    """Represents an OJS job state change event."""

    job_type: str
    job_id: str
    previous_status: str
    new_status: str
    entry: OJSOutboxEntry | None = None


# Type for state change callback: Callable[[JobStateEvent], None]
StateChangeCallback = Callable[[JobStateEvent], None]


class OJSEventListener:
    """Listens for OJS outbox entry state changes and dispatches callbacks.

    Registers SQLAlchemy attribute change listeners on OJSOutboxEntry.status
    to detect when entries transition between states (e.g., pending → published,
    pending → failed).

    Usage::
        listener = OJSEventListener()

        @listener.on_state_change("published")
        def on_published(event: JobStateEvent):
            logger.info("Job %s published: %s", event.job_id, event.job_type)

        @listener.on_state_change("failed")
        def on_failed(event: JobStateEvent):
            send_alert(f"Job {event.job_type} failed to publish")

        # Install on a session or mapper
        listener.install()
    """

    def __init__(self) -> None:
        self._callbacks: dict[str, list[StateChangeCallback]] = {}
        self._installed: bool = False

    def on_state_change(
        self, target_status: str
    ) -> Callable[[StateChangeCallback], StateChangeCallback]:
        """Decorator to register a callback for a specific status transition.

        Args:
            target_status: The new status to listen for (e.g., "published", "failed").

        Returns:
            Decorator that registers the callback.
        """

        def decorator(fn: StateChangeCallback) -> StateChangeCallback:
            self._callbacks.setdefault(target_status, []).append(fn)
            return fn

        return decorator

    def add_callback(self, target_status: str, callback: StateChangeCallback) -> None:
        """Register a callback programmatically."""
        self._callbacks.setdefault(target_status, []).append(callback)

    @property
    def registered_statuses(self) -> list[str]:
        """Return the list of statuses that have registered callbacks."""
        return list(self._callbacks.keys())

    def get_callbacks(self, status: str) -> list[StateChangeCallback]:
        """Return callbacks for a given status."""
        return self._callbacks.get(status, [])

    def install(self) -> None:
        """Install SQLAlchemy attribute listeners on OJSOutboxEntry.status.

        This sets up a `set` event listener on the mapped `status` attribute
        so that callbacks fire whenever status is changed on an entry.
        """
        if self._installed:
            return

        listener_ref = self  # capture for closure

        @event.listens_for(OJSOutboxEntry.status, "set")
        def _on_status_change(
            target: OJSOutboxEntry,
            value: str,
            oldvalue: str,
            initiator: Any,
        ) -> None:
            if oldvalue == value:
                return
            callbacks = listener_ref._callbacks.get(value, [])
            if not callbacks:
                return

            evt = JobStateEvent(
                job_type=target.job_type,
                job_id=target.id or "",
                previous_status=str(oldvalue) if oldvalue else "",
                new_status=value,
                entry=target,
            )
            listener_ref._dispatch(evt, callbacks)

        self._installed = True

    def notify(self, entry: OJSOutboxEntry, new_status: str) -> None:
        """Manually fire callbacks for a state change.

        Useful when state changes happen via bulk UPDATE statements
        that bypass attribute events.
        """
        old_status = entry.status
        callbacks = self._callbacks.get(new_status, [])
        if not callbacks:
            return

        evt = JobStateEvent(
            job_type=entry.job_type,
            job_id=entry.id or "",
            previous_status=old_status,
            new_status=new_status,
            entry=entry,
        )
        self._dispatch(evt, callbacks)

    @staticmethod
    def _dispatch(evt: JobStateEvent, callbacks: list[StateChangeCallback]) -> None:
        """Invoke each callback, isolating and logging callback failures."""
        for cb in callbacks:
            try:
                cb(evt)
            except Exception:
                logger.exception("Event callback error for %s → %s", evt.job_type, evt.new_status)
