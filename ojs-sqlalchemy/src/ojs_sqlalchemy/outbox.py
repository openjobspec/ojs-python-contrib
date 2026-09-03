"""Outbox pattern implementation for reliable OJS job delivery.

The outbox pattern writes job enqueue requests to a database table within
the same transaction as your business data. A separate publisher process
polls the outbox table and delivers jobs to OJS, ensuring at-least-once
delivery even if the OJS server is temporarily unavailable.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

from .models import OJSOutboxEntry

logger = logging.getLogger(__name__)


class OJSOutbox:
    """Mixin-style helper for writing outbox entries within a transaction.

    Usage::

        outbox = OJSOutbox()
        outbox.add(session, "email.send", ["user@example.com", "welcome"])
        session.commit()  # entry is atomically written with other changes
    """

    def add(
        self,
        session: Session,
        job_type: str,
        args: list[Any] | None = None,
        *,
        queue: str = "default",
        meta: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> OJSOutboxEntry:
        """Add a job to the outbox within the current transaction.

        Args:
            session: Active SQLAlchemy session.
            job_type: Dot-namespaced job type.
            args: Positional arguments for the job handler.
            queue: Target queue name.
            meta: Extensible key-value metadata.
            priority: Job priority.

        Returns:
            The created OJSOutboxEntry (not yet committed).
        """
        entry = OJSOutboxEntry(
            job_type=job_type,
            args_json=json.dumps(args or []),
            queue=queue,
            meta_json=json.dumps(meta or {}),
            priority=priority,
        )
        session.add(entry)
        return entry


class OutboxPublisher:
    """Polls the outbox table and publishes pending jobs to OJS.

    Usage::

        publisher = OutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=SessionLocal,
        )
        publisher.publish_pending(batch_size=100)

    For continuous operation, call ``run_forever()`` which polls at a
    configurable interval.
    """

    def __init__(
        self,
        ojs_url: str,
        session_factory: Any,
        *,
        batch_size: int = 100,
        poll_interval: float = 1.0,
    ) -> None:
        """Initialize the outbox publisher.

        Args:
            ojs_url: Base URL of the OJS server.
            session_factory: Callable that returns a new SQLAlchemy Session.
            batch_size: Maximum entries to process per poll cycle.
            poll_interval: Seconds between poll cycles in ``run_forever()``.
        """
        self._ojs_url = ojs_url
        self._session_factory = session_factory
        self._batch_size = batch_size
        self._poll_interval = poll_interval

    def publish_pending(self, batch_size: int | None = None) -> int:
        """Publish pending outbox entries to OJS.

        Args:
            batch_size: Override the default batch size.

        Returns:
            Number of entries successfully published.
        """
        limit = batch_size or self._batch_size
        published = 0

        with self._session_factory() as session:
            stmt = (
                select(OJSOutboxEntry)
                .where(OJSOutboxEntry.status == "pending")
                .order_by(OJSOutboxEntry.created_at)
                .limit(limit)
            )
            entries = list(session.execute(stmt).scalars())

            if not entries:
                return 0

            import ojs

            with ojs.SyncClient(self._ojs_url) as client:
                for entry in entries:
                    try:
                        client.enqueue(
                            entry.job_type,
                            entry.args,
                            queue=entry.queue,
                            meta=entry.meta or None,
                            priority=entry.priority,
                        )
                        session.execute(
                            update(OJSOutboxEntry)
                            .where(OJSOutboxEntry.id == entry.id)
                            .values(
                                status="published",
                                published_at=datetime.now(UTC),
                            )
                        )
                        published += 1
                    except Exception:
                        logger.exception("Failed to publish outbox entry %s", entry.id)
                        session.execute(
                            update(OJSOutboxEntry)
                            .where(OJSOutboxEntry.id == entry.id)
                            .values(status="failed")
                        )

            session.commit()

        logger.info("Published %d/%d outbox entries", published, len(entries))
        return published

    def cleanup_published(self, *, older_than_seconds: int = 3600) -> int:
        """Delete published outbox entries older than the given threshold.

        Args:
            older_than_seconds: Age threshold in seconds. Default: 1 hour.

        Returns:
            Number of entries deleted.
        """
        cutoff = datetime.fromtimestamp(time.time() - older_than_seconds, tz=UTC)

        with self._session_factory() as session:
            stmt = (
                select(OJSOutboxEntry)
                .where(OJSOutboxEntry.status == "published")
                .where(OJSOutboxEntry.published_at < cutoff)
            )
            entries = list(session.execute(stmt).scalars())
            for entry in entries:
                session.delete(entry)
            session.commit()

        return len(entries)

    def run_forever(self) -> None:
        """Continuously poll and publish outbox entries.

        Blocks indefinitely. Intended to be run in a dedicated thread
        or process.
        """
        logger.info(
            "Outbox publisher started (interval=%.1fs, batch=%d)",
            self._poll_interval,
            self._batch_size,
        )
        while True:
            try:
                self.publish_pending()
            except Exception:
                logger.exception("Error in outbox publisher poll cycle")
            time.sleep(self._poll_interval)
