"""Tests for the OJS event listener system."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ojs_sqlalchemy.events import JobStateEvent, OJSEventListener
from ojs_sqlalchemy.models import Base, OJSOutboxEntry


def _make_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestOJSEventListener:
    """Tests for OJSEventListener."""

    def test_register_callback_with_decorator(self) -> None:
        """Decorator registers a callback for the target status."""
        listener = OJSEventListener()

        @listener.on_state_change("published")
        def on_published(event: JobStateEvent) -> None:
            pass

        assert on_published in listener.get_callbacks("published")

    def test_register_callback_programmatically(self) -> None:
        """add_callback registers a callback without decorator syntax."""
        listener = OJSEventListener()
        cb = MagicMock()
        listener.add_callback("failed", cb)
        assert cb in listener.get_callbacks("failed")

    def test_registered_statuses(self) -> None:
        """registered_statuses returns all statuses with callbacks."""
        listener = OJSEventListener()
        listener.add_callback("published", MagicMock())
        listener.add_callback("failed", MagicMock())

        statuses = listener.registered_statuses
        assert sorted(statuses) == ["failed", "published"]

    def test_get_callbacks(self) -> None:
        """get_callbacks returns the list of callbacks for a status."""
        listener = OJSEventListener()
        cb1 = MagicMock()
        cb2 = MagicMock()
        listener.add_callback("published", cb1)
        listener.add_callback("published", cb2)

        callbacks = listener.get_callbacks("published")
        assert callbacks == [cb1, cb2]

    def test_get_callbacks_unknown_returns_empty(self) -> None:
        """get_callbacks returns empty list for unregistered status."""
        listener = OJSEventListener()
        assert listener.get_callbacks("nonexistent") == []

    def test_notify_fires_callbacks(self) -> None:
        """notify() fires registered callbacks with correct event data."""
        listener = OJSEventListener()
        cb = MagicMock()
        listener.add_callback("published", cb)

        entry = OJSOutboxEntry(
            id="test-id-123",
            job_type="email.send",
            status="pending",
        )

        listener.notify(entry, "published")

        cb.assert_called_once()
        evt = cb.call_args[0][0]
        assert isinstance(evt, JobStateEvent)
        assert evt.job_type == "email.send"
        assert evt.job_id == "test-id-123"
        assert evt.previous_status == "pending"
        assert evt.new_status == "published"
        assert evt.entry is entry

    def test_notify_with_different_statuses(self) -> None:
        """notify() only fires callbacks matching the target status."""
        listener = OJSEventListener()
        published_cb = MagicMock()
        failed_cb = MagicMock()
        listener.add_callback("published", published_cb)
        listener.add_callback("failed", failed_cb)

        entry = OJSOutboxEntry(
            id="test-id-456",
            job_type="report.generate",
            status="pending",
        )

        listener.notify(entry, "failed")

        published_cb.assert_not_called()
        failed_cb.assert_called_once()
        evt = failed_cb.call_args[0][0]
        assert evt.new_status == "failed"

    def test_notify_callback_error_handled(self, caplog: pytest.LogCaptureFixture) -> None:
        """notify() catches and logs exceptions from callbacks."""
        listener = OJSEventListener()
        bad_cb = MagicMock(side_effect=ValueError("boom"))
        listener.add_callback("published", bad_cb)

        entry = OJSOutboxEntry(
            id="err-id",
            job_type="crash.job",
            status="pending",
        )

        # Should not raise
        listener.notify(entry, "published")
        bad_cb.assert_called_once()

    def test_install_attribute_listener(self) -> None:
        """install() sets up SQLAlchemy attribute listeners that fire callbacks."""
        listener = OJSEventListener()
        cb = MagicMock()
        listener.add_callback("published", cb)
        listener.install()

        factory = _make_session_factory()

        with factory() as session:
            entry = OJSOutboxEntry(
                job_type="email.send",
                status="pending",
            )
            session.add(entry)
            session.flush()

            # Trigger attribute change
            entry.status = "published"

        cb.assert_called_once()
        evt = cb.call_args[0][0]
        assert isinstance(evt, JobStateEvent)
        assert evt.job_type == "email.send"
        assert evt.new_status == "published"
        assert evt.previous_status == "pending"
