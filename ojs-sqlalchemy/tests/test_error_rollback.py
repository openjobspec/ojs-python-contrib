"""Tests for error rollback behavior in OJS SQLAlchemy integration."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

from ojs_sqlalchemy.enqueue import enqueue_after_commit  # noqa: E402
from ojs_sqlalchemy.models import Base, OJSOutboxEntry  # noqa: E402
from ojs_sqlalchemy.outbox import OJSOutbox  # noqa: E402


def _make_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestOutboxRollback:
    """Tests for outbox entry rollback on transaction failure."""

    def test_outbox_entries_discarded_on_rollback(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["user@example.com"])
            outbox.add(session, "report.generate", [42])
            session.rollback()

        with factory() as session:
            entries = list(session.execute(select(OJSOutboxEntry)).scalars())
            assert len(entries) == 0

    def test_partial_commit_after_rollback(self) -> None:
        """After a rollback, a fresh commit should work normally."""
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["fail"])
            session.rollback()

        with factory() as session:
            outbox.add(session, "email.send", ["success"])
            session.commit()

        with factory() as session:
            entries = list(session.execute(select(OJSOutboxEntry)).scalars())
            assert len(entries) == 1
            assert entries[0].args == ["success"]


class TestEnqueueAfterCommitRollback:
    """Tests for enqueue_after_commit rollback behavior."""

    def test_listener_not_fired_on_rollback(self) -> None:
        factory = _make_session_factory()

        mock_client = MagicMock()
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            with factory() as session:
                enqueue_after_commit(
                    session, "http://localhost:8080", "email.send", ["user@example.com"]
                )
                session.rollback()

            mock_client.enqueue.assert_not_called()
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_enqueue_error_does_not_affect_db(self) -> None:
        """If enqueue fails after commit, the DB transaction is unaffected."""
        factory = _make_session_factory()

        mock_client = MagicMock()
        mock_client.enqueue.side_effect = ConnectionError("OJS server down")
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            outbox = OJSOutbox()
            with factory() as session:
                # Add an outbox entry (this goes to DB)
                outbox.add(session, "db.entry", [1])
                # Also register an after-commit enqueue (this fails on send)
                enqueue_after_commit(
                    session, "http://localhost:8080", "email.send", ["user@example.com"]
                )
                session.commit()  # commit succeeds; enqueue failure is logged

            # The DB entry should still be persisted
            with factory() as session:
                entries = list(session.execute(select(OJSOutboxEntry)).scalars())
                assert len(entries) == 1
                assert entries[0].job_type == "db.entry"
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_multiple_listeners_partial_failure(self) -> None:
        """If one enqueue fails, the other should still succeed."""
        factory = _make_session_factory()

        call_count = 0
        mock_client = MagicMock()

        def side_effect(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First fails")
            return MagicMock()

        mock_client.enqueue.side_effect = side_effect
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            with factory() as session:
                enqueue_after_commit(session, "http://localhost:8080", "job.1", [1])
                enqueue_after_commit(session, "http://localhost:8080", "job.2", [2])
                session.commit()

            # Both listeners should have been called
            assert mock_client.enqueue.call_count == 2
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]
