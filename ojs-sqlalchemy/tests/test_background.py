"""Tests for the background outbox publisher."""

from __future__ import annotations

import sys
import time
from types import ModuleType
from unittest.mock import MagicMock

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from ojs_sqlalchemy.background import BackgroundOutboxPublisher, PublishStats  # noqa: E402
from ojs_sqlalchemy.models import Base  # noqa: E402


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestBackgroundOutboxPublisher:
    """Tests for BackgroundOutboxPublisher."""

    def test_background_publisher_not_running_initially(self) -> None:
        """Publisher is not running before start() is called."""
        factory = _make_session_factory()
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        assert publisher.is_running is False

    def test_background_publisher_start_stop(self) -> None:
        """Publisher starts a daemon thread and stops cleanly."""
        factory = _make_session_factory()
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
            flush_interval=0.1,
        )
        publisher.start()
        assert publisher.is_running is True

        publisher.stop(timeout=2.0)
        assert publisher.is_running is False

    def test_background_publisher_double_start_raises(self) -> None:
        """Starting an already-running publisher raises RuntimeError."""
        factory = _make_session_factory()
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
            flush_interval=0.1,
        )
        publisher.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                publisher.start()
        finally:
            publisher.stop(timeout=2.0)

    def test_flush_now_calls_publish_pending(self) -> None:
        """flush_now() delegates to the underlying OutboxPublisher."""
        factory = _make_session_factory()
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        # Empty outbox → should return 0
        count = publisher.flush_now()
        assert count == 0

    def test_stats_tracking(self) -> None:
        """Background publisher tracks stats across cycles."""
        factory = _make_session_factory()
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
            flush_interval=0.05,
        )
        # Mock publish_pending to avoid real DB calls from the background thread
        publisher._publisher.publish_pending = MagicMock(return_value=0)  # type: ignore[method-assign]
        publisher.start()
        # Let a few cycles run
        time.sleep(0.3)
        publisher.stop(timeout=2.0)

        assert publisher.stats.cycles > 0
        assert publisher.stats.total_errors == 0

    def test_stats_to_dict(self) -> None:
        """PublishStats.to_dict() returns a plain dict with expected keys."""
        stats = PublishStats()
        stats.total_published = 10
        stats.total_errors = 2
        stats.cycles = 5
        stats.last_publish_count = 3

        result = stats.to_dict()
        assert result == {
            "total_published": 10,
            "total_errors": 2,
            "cycles": 5,
            "last_publish_count": 3,
        }
