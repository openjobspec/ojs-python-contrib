"""Health check utilities for OJS + SQLAlchemy integration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import OJSOutboxEntry

logger = logging.getLogger(__name__)


class OutboxHealthCheck:
    """Health check for the OJS outbox system.

    Provides methods to inspect outbox health: pending count, failed count,
    oldest pending entry age, and publisher lag.

    Usage::
        health = OutboxHealthCheck(session_factory=SessionLocal)
        report = health.check()
        # {"healthy": True, "pending": 5, "failed": 0, "oldest_pending_age_seconds": 12.3}
    """

    def __init__(
        self,
        session_factory: Any,
        *,
        max_pending_threshold: int = 1000,
        max_age_seconds: float = 300.0,
    ) -> None:
        self._session_factory = session_factory
        self._max_pending = max_pending_threshold
        self._max_age = max_age_seconds

    def check(self) -> dict[str, Any]:
        """Run health check and return a status dict."""
        with self._session_factory() as session:
            pending_count = self._count_by_status(session, "pending")
            failed_count = self._count_by_status(session, "failed")
            published_count = self._count_by_status(session, "published")
            oldest_age = self._oldest_pending_age(session)

        healthy = pending_count <= self._max_pending and (
            oldest_age is None or oldest_age <= self._max_age
        )

        return {
            "healthy": healthy,
            "pending": pending_count,
            "failed": failed_count,
            "published": published_count,
            "oldest_pending_age_seconds": round(oldest_age, 2) if oldest_age else None,
            "thresholds": {
                "max_pending": self._max_pending,
                "max_age_seconds": self._max_age,
            },
        }

    @staticmethod
    def _count_by_status(session: Session, status: str) -> int:
        """Count outbox entries with the given status."""
        result = session.execute(select(func.count()).where(OJSOutboxEntry.status == status))
        return result.scalar() or 0

    @staticmethod
    def _oldest_pending_age(session: Session) -> float | None:
        """Return the age in seconds of the oldest pending entry, or None."""
        result = session.execute(
            select(func.min(OJSOutboxEntry.created_at)).where(OJSOutboxEntry.status == "pending")
        )
        oldest = result.scalar()
        if oldest is None:
            return None
        now = datetime.now(UTC)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=UTC)
        return (now - oldest).total_seconds()
