"""Tests for concurrent enqueue and session integration."""

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

from ojs_sqlalchemy.enqueue import enqueue_after_commit
from ojs_sqlalchemy.models import Base, OJSOutboxEntry
from ojs_sqlalchemy.outbox import OJSOutbox


def _make_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestMultipleEnqueuesPerSession:
    """Tests for multiple enqueues within a single session."""

    def test_multiple_outbox_entries_in_one_transaction(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["user1@example.com"])
            outbox.add(session, "email.send", ["user2@example.com"])
            outbox.add(session, "report.generate", [42])
            session.commit()

        with factory() as session:
            entries = list(session.execute(select(OJSOutboxEntry)).scalars())
            assert len(entries) == 3

    def test_multiple_after_commit_listeners(self) -> None:
        factory = _make_session_factory()
        calls: list[str] = []

        mock_client = MagicMock()
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

            # Both should have fired (each registers a separate listener with once=True)
            assert mock_client.enqueue.call_count == 2
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_outbox_entries_have_unique_ids(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            e1 = outbox.add(session, "job.1", [1])
            e2 = outbox.add(session, "job.2", [2])
            session.commit()
            assert e1.id != e2.id


class TestSessionIntegration:
    """Tests for OJS integration with SQLAlchemy session lifecycle."""

    def test_outbox_with_other_models(self) -> None:
        """Outbox entries can coexist with other model operations."""
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(session, "order.process", [123], queue="orders")
            session.commit()
            assert entry.status == "pending"

    def test_outbox_entry_queryable(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["a@b.com"], queue="email")
            outbox.add(session, "report.generate", [42], queue="reports")
            session.commit()

        with factory() as session:
            email_entries = list(
                session.execute(
                    select(OJSOutboxEntry).where(OJSOutboxEntry.queue == "email")
                ).scalars()
            )
            assert len(email_entries) == 1
            assert email_entries[0].job_type == "email.send"

    def test_outbox_entry_filterable_by_status(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "job.1", [1])
            outbox.add(session, "job.2", [2])
            session.commit()

        with factory() as session:
            pending = list(
                session.execute(
                    select(OJSOutboxEntry).where(OJSOutboxEntry.status == "pending")
                ).scalars()
            )
            assert len(pending) == 2

            published = list(
                session.execute(
                    select(OJSOutboxEntry).where(OJSOutboxEntry.status == "published")
                ).scalars()
            )
            assert len(published) == 0
