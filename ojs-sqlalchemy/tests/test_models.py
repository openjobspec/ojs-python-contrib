"""Tests for OJSOutboxEntry model serialization and properties."""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

_mock_ojs = ModuleType("ojs")
_mock_ojs.SyncClient = MagicMock  # type: ignore[attr-defined]
_mock_ojs.Client = MagicMock  # type: ignore[attr-defined]
sys.modules.setdefault("ojs", _mock_ojs)

from ojs_sqlalchemy.models import Base, OJSOutboxEntry


def _make_session() -> sessionmaker[Session]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestOutboxEntryModel:
    """Tests for OJSOutboxEntry model fields and defaults."""

    def test_default_values(self) -> None:
        factory = _make_session()
        with factory() as session:
            entry = OJSOutboxEntry(job_type="email.send")
            session.add(entry)
            session.commit()

            assert entry.id is not None
            assert len(entry.id) == 36  # UUID format
            assert entry.job_type == "email.send"
            assert entry.args_json == "[]"
            assert entry.queue == "default"
            assert entry.meta_json == "{}"
            assert entry.priority == 0
            assert entry.status == "pending"
            assert entry.published_at is None

    def test_created_at_auto_set(self) -> None:
        factory = _make_session()
        with factory() as session:
            entry = OJSOutboxEntry(job_type="email.send")
            session.add(entry)
            session.commit()
            assert entry.created_at is not None


class TestArgsProperty:
    """Tests for the args property (JSON serialization)."""

    def test_args_getter_empty(self) -> None:
        entry = OJSOutboxEntry(job_type="test", args_json="[]")
        assert entry.args == []

    def test_args_getter_with_values(self) -> None:
        entry = OJSOutboxEntry(
            job_type="test",
            args_json='["user@example.com", 42, true]',
        )
        assert entry.args == ["user@example.com", 42, True]

    def test_args_setter(self) -> None:
        entry = OJSOutboxEntry(job_type="test")
        entry.args = ["hello", "world"]
        assert entry.args_json == '["hello", "world"]'
        assert entry.args == ["hello", "world"]

    def test_args_roundtrip(self) -> None:
        factory = _make_session()
        with factory() as session:
            entry = OJSOutboxEntry(job_type="test")
            entry.args = [1, "two", {"three": 3}]
            session.add(entry)
            session.commit()

            fetched = session.execute(
                select(OJSOutboxEntry).where(OJSOutboxEntry.id == entry.id)
            ).scalar_one()
            assert fetched.args == [1, "two", {"three": 3}]


class TestMetaProperty:
    """Tests for the meta property (JSON serialization)."""

    def test_meta_getter_empty(self) -> None:
        entry = OJSOutboxEntry(job_type="test", meta_json="{}")
        assert entry.meta == {}

    def test_meta_getter_with_values(self) -> None:
        entry = OJSOutboxEntry(
            job_type="test",
            meta_json='{"tenant": "acme", "priority": 5}',
        )
        assert entry.meta == {"tenant": "acme", "priority": 5}

    def test_meta_setter(self) -> None:
        entry = OJSOutboxEntry(job_type="test")
        entry.meta = {"source": "api", "version": 2}
        parsed = json.loads(entry.meta_json)
        assert parsed == {"source": "api", "version": 2}

    def test_meta_roundtrip(self) -> None:
        factory = _make_session()
        with factory() as session:
            entry = OJSOutboxEntry(job_type="test")
            entry.meta = {"complex": {"nested": [1, 2, 3]}}
            session.add(entry)
            session.commit()

            fetched = session.execute(
                select(OJSOutboxEntry).where(OJSOutboxEntry.id == entry.id)
            ).scalar_one()
            assert fetched.meta == {"complex": {"nested": [1, 2, 3]}}


class TestOutboxEntryRepr:
    """Tests for OJSOutboxEntry string representation."""

    def test_repr_contains_job_type(self) -> None:
        entry = OJSOutboxEntry(job_type="email.send", status="pending")
        r = repr(entry)
        assert "email.send" in r
        assert "pending" in r

    def test_repr_contains_status(self) -> None:
        entry = OJSOutboxEntry(job_type="test", status="published")
        r = repr(entry)
        assert "published" in r
