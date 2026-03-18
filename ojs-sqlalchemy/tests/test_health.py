"""Tests for the outbox health check."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest.mock import MagicMock

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ojs_sqlalchemy.health import OutboxHealthCheck
from ojs_sqlalchemy.models import Base, OJSOutboxEntry


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestOutboxHealthCheck:
    """Tests for OutboxHealthCheck."""

    def test_health_check_healthy_empty_outbox(self) -> None:
        """Empty outbox reports healthy."""
        factory = _make_session_factory()
        health = OutboxHealthCheck(session_factory=factory)
        report = health.check()

        assert report["healthy"] is True
        assert report["pending"] == 0
        assert report["failed"] == 0
        assert report["published"] == 0
        assert report["oldest_pending_age_seconds"] is None

    def test_health_check_with_pending_entries(self) -> None:
        """Outbox with few pending entries is healthy."""
        factory = _make_session_factory()

        with factory() as session:
            for i in range(3):
                session.add(OJSOutboxEntry(
                    job_type=f"job.{i}",
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                ))
            session.commit()

        health = OutboxHealthCheck(session_factory=factory, max_pending_threshold=10)
        report = health.check()

        assert report["healthy"] is True
        assert report["pending"] == 3
        assert report["oldest_pending_age_seconds"] is not None

    def test_health_check_unhealthy_too_many_pending(self) -> None:
        """Outbox exceeding max_pending_threshold is unhealthy."""
        factory = _make_session_factory()

        with factory() as session:
            for i in range(5):
                session.add(OJSOutboxEntry(
                    job_type=f"job.{i}",
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                ))
            session.commit()

        health = OutboxHealthCheck(
            session_factory=factory,
            max_pending_threshold=3,
        )
        report = health.check()

        assert report["healthy"] is False
        assert report["pending"] == 5

    def test_health_check_with_failed_entries(self) -> None:
        """Health check counts failed entries separately."""
        factory = _make_session_factory()

        with factory() as session:
            session.add(OJSOutboxEntry(
                job_type="good.job",
                status="pending",
                created_at=datetime.now(timezone.utc),
            ))
            session.add(OJSOutboxEntry(
                job_type="bad.job",
                status="failed",
                created_at=datetime.now(timezone.utc),
            ))
            session.commit()

        health = OutboxHealthCheck(session_factory=factory)
        report = health.check()

        assert report["pending"] == 1
        assert report["failed"] == 1

    def test_health_check_counts_published(self) -> None:
        """Health check counts published entries."""
        factory = _make_session_factory()

        with factory() as session:
            session.add(OJSOutboxEntry(
                job_type="done.job",
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            ))
            session.add(OJSOutboxEntry(
                job_type="done.job2",
                status="published",
                created_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
            ))
            session.commit()

        health = OutboxHealthCheck(session_factory=factory)
        report = health.check()

        assert report["published"] == 2
        assert report["pending"] == 0
        assert report["healthy"] is True
