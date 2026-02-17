"""Tests for enqueue_after_commit and outbox pattern."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

# Create a mock ojs module so imports don't fail
_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

from ojs_sqlalchemy.enqueue import enqueue_after_commit
from ojs_sqlalchemy.models import Base, OJSOutboxEntry
from ojs_sqlalchemy.outbox import OJSOutbox


def _make_session() -> tuple[sessionmaker[Session], None]:
    """Create an in-memory SQLite engine and session factory."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory, None


class TestEnqueueAfterCommit:
    """Tests for the enqueue_after_commit helper."""

    def test_enqueue_fires_after_commit(self) -> None:
        """Job is enqueued only when the session commits."""
        factory, _ = _make_session()

        mock_client = MagicMock()
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        # Patch ojs.SyncClient at the module level
        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            with factory() as session:
                enqueue_after_commit(
                    session,
                    "http://localhost:8080",
                    "email.send",
                    ["user@example.com", "welcome"],
                    queue="email",
                    meta={"tenant": "acme"},
                )
                # Not yet committed — enqueue should NOT have been called
                mock_client.enqueue.assert_not_called()

                session.commit()

            # After commit — enqueue should have been called
            mock_client.enqueue.assert_called_once_with(
                "email.send",
                ["user@example.com", "welcome"],
                queue="email",
                priority=0,
                meta={"tenant": "acme"},
            )
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_enqueue_not_called_on_rollback(self) -> None:
        """Job is NOT enqueued when the session is rolled back."""
        factory, _ = _make_session()

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
                    session,
                    "http://localhost:8080",
                    "email.send",
                    ["user@example.com"],
                )
                session.rollback()

            # After rollback — enqueue should NOT have been called
            mock_client.enqueue.assert_not_called()
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_enqueue_with_default_args(self) -> None:
        """Enqueue works with minimal arguments."""
        factory, _ = _make_session()

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
                    session,
                    "http://localhost:8080",
                    "data.process",
                )
                session.commit()

            mock_client.enqueue.assert_called_once_with(
                "data.process",
                [],
                queue="default",
                priority=0,
            )
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]


class TestOJSOutbox:
    """Tests for the outbox pattern."""

    def test_outbox_entry_creation(self) -> None:
        """Outbox entries are created in the same transaction."""
        factory, _ = _make_session()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(
                session,
                "email.send",
                ["user@example.com", "welcome"],
                queue="email",
                meta={"tenant": "acme"},
                priority=5,
            )
            session.commit()

            assert entry.id is not None
            assert entry.job_type == "email.send"
            assert entry.args == ["user@example.com", "welcome"]
            assert entry.queue == "email"
            assert entry.meta == {"tenant": "acme"}
            assert entry.priority == 5
            assert entry.status == "pending"

    def test_outbox_entry_not_persisted_on_rollback(self) -> None:
        """Outbox entries are discarded when the transaction rolls back."""
        factory, _ = _make_session()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["user@example.com"])
            session.rollback()

        with factory() as session:
            result = list(session.execute(select(OJSOutboxEntry)).scalars())
            assert len(result) == 0

    def test_outbox_entry_defaults(self) -> None:
        """Outbox entries use sensible defaults."""
        factory, _ = _make_session()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(session, "data.process")
            session.commit()

            assert entry.args == []
            assert entry.queue == "default"
            assert entry.meta == {}
            assert entry.priority == 0
            assert entry.status == "pending"
            assert entry.published_at is None

    def test_outbox_entry_repr(self) -> None:
        """OJSOutboxEntry has a useful repr."""
        factory, _ = _make_session()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(session, "email.send")
            session.commit()

            r = repr(entry)
            assert "email.send" in r
            assert "pending" in r
