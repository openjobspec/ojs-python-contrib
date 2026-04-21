"""Tests for the OutboxPublisher flush mechanism."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import ModuleType
from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

from ojs_sqlalchemy.models import Base, OJSOutboxEntry  # noqa: E402
from ojs_sqlalchemy.outbox import OJSOutbox, OutboxPublisher  # noqa: E402


def _make_session_factory() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestOutboxPublishPending:
    """Tests for OutboxPublisher.publish_pending()."""

    def test_publish_empty_outbox(self) -> None:
        factory = _make_session_factory()
        publisher = OutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        count = publisher.publish_pending()
        assert count == 0

    def test_publish_single_entry(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            outbox.add(session, "email.send", ["user@example.com"], queue="email")
            session.commit()

        mock_client = MagicMock()
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            publisher = OutboxPublisher(
                ojs_url="http://localhost:8080",
                session_factory=factory,
            )
            count = publisher.publish_pending()
            assert count == 1
            mock_client.enqueue.assert_called_once()
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_publish_marks_entry_as_published(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(session, "email.send", ["user@example.com"])
            session.commit()
            entry_id = entry.id

        mock_client = MagicMock()
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            publisher = OutboxPublisher(
                ojs_url="http://localhost:8080",
                session_factory=factory,
            )
            publisher.publish_pending()

            with factory() as session:
                updated = session.execute(
                    select(OJSOutboxEntry).where(OJSOutboxEntry.id == entry_id)
                ).scalar_one()
                assert updated.status == "published"
                assert updated.published_at is not None
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_publish_failed_entry_marked(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            entry = outbox.add(session, "email.send", ["fail"])
            session.commit()
            entry_id = entry.id

        mock_client = MagicMock()
        mock_client.enqueue.side_effect = ConnectionError("refused")
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            publisher = OutboxPublisher(
                ojs_url="http://localhost:8080",
                session_factory=factory,
            )
            count = publisher.publish_pending()
            assert count == 0

            with factory() as session:
                updated = session.execute(
                    select(OJSOutboxEntry).where(OJSOutboxEntry.id == entry_id)
                ).scalar_one()
                assert updated.status == "failed"
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]

    def test_publish_respects_batch_size(self) -> None:
        factory = _make_session_factory()
        outbox = OJSOutbox()

        with factory() as session:
            for i in range(5):
                outbox.add(session, f"job.{i}", [i])
            session.commit()

        mock_client = MagicMock()
        mock_sync_client = MagicMock()
        mock_sync_client.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_sync_client.return_value.__exit__ = MagicMock(return_value=False)

        import ojs

        original = getattr(ojs, "SyncClient", None)
        ojs.SyncClient = mock_sync_client  # type: ignore[attr-defined]
        try:
            publisher = OutboxPublisher(
                ojs_url="http://localhost:8080",
                session_factory=factory,
                batch_size=3,
            )
            count = publisher.publish_pending()
            assert count == 3
            assert mock_client.enqueue.call_count == 3
        finally:
            if original is not None:
                ojs.SyncClient = original  # type: ignore[attr-defined]


class TestOutboxCleanup:
    """Tests for OutboxPublisher.cleanup_published()."""

    def test_cleanup_removes_old_published(self) -> None:
        factory = _make_session_factory()

        with factory() as session:
            entry = OJSOutboxEntry(
                job_type="old.job",
                status="published",
                published_at=datetime(2020, 1, 1, tzinfo=UTC),
            )
            session.add(entry)
            session.commit()

        publisher = OutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        deleted = publisher.cleanup_published(older_than_seconds=60)
        assert deleted == 1

        with factory() as session:
            remaining = list(session.execute(select(OJSOutboxEntry)).scalars())
            assert len(remaining) == 0

    def test_cleanup_keeps_recent_published(self) -> None:
        factory = _make_session_factory()

        with factory() as session:
            entry = OJSOutboxEntry(
                job_type="recent.job",
                status="published",
                published_at=datetime.now(UTC),
            )
            session.add(entry)
            session.commit()

        publisher = OutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        deleted = publisher.cleanup_published(older_than_seconds=3600)
        assert deleted == 0

    def test_cleanup_ignores_pending(self) -> None:
        factory = _make_session_factory()

        with factory() as session:
            entry = OJSOutboxEntry(
                job_type="pending.job",
                status="pending",
            )
            session.add(entry)
            session.commit()

        publisher = OutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=factory,
        )
        deleted = publisher.cleanup_published(older_than_seconds=0)
        assert deleted == 0
