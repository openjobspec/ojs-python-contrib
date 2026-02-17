"""Tests for enqueue, enqueue_at, enqueue_after_commit, and enqueue_batch."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from django.db import transaction

import ojs

from ojs_django.backend import enqueue, enqueue_after_commit, enqueue_at, enqueue_batch
from ojs_django.conf import reset_settings


@pytest.fixture(autouse=True)
def _reset_client() -> None:  # type: ignore[misc]
    """Reset the module-level cached client between tests."""
    import ojs_django.backend as mod

    mod._sync_client = None
    reset_settings()


@pytest.mark.django_db(transaction=True)
def test_enqueue_after_commit_defers_until_commit() -> None:
    """Job enqueue should only happen when the transaction commits."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_client.enqueue.return_value = MagicMock(spec=ojs.Job)

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        with transaction.atomic():
            enqueue_after_commit("email.send", ["user@test.com"], queue="email")
            mock_client.enqueue.assert_not_called()

        mock_client.enqueue.assert_called_once_with(
            "email.send",
            ["user@test.com"],
            queue="email",
            meta=None,
        )


@pytest.mark.django_db(transaction=True)
def test_enqueue_after_commit_not_called_on_rollback() -> None:
    """Job enqueue should NOT happen if the transaction rolls back."""
    mock_client = MagicMock(spec=ojs.SyncClient)

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        try:
            with transaction.atomic():
                enqueue_after_commit("email.send", ["user@test.com"])
                raise ValueError("force rollback")
        except ValueError:
            pass

        mock_client.enqueue.assert_not_called()


def test_enqueue_immediate() -> None:
    """enqueue() should call the client immediately."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_job = MagicMock(spec=ojs.Job)
    mock_client.enqueue.return_value = mock_job

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        result = enqueue("email.send", "user@test.com", "welcome", queue="email")

    assert result == mock_job
    mock_client.enqueue.assert_called_once_with(
        "email.send",
        ["user@test.com", "welcome"],
        queue="email",
        meta=None,
        priority=0,
        retry=None,
        tags=None,
    )


def test_enqueue_at_with_datetime() -> None:
    """enqueue_at() should pass delay_until to the client."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_client.enqueue.return_value = MagicMock(spec=ojs.Job)
    scheduled = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        enqueue_at("report.gen", scheduled, "monthly")

    mock_client.enqueue.assert_called_once()
    call_kwargs = mock_client.enqueue.call_args
    assert call_kwargs.kwargs["delay_until"] == "2025-01-15T10:00:00+00:00"


def test_enqueue_at_with_string() -> None:
    """enqueue_at() should accept ISO string."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_client.enqueue.return_value = MagicMock(spec=ojs.Job)

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        enqueue_at("report.gen", "2025-01-15T10:00:00Z", "monthly")

    call_kwargs = mock_client.enqueue.call_args
    assert call_kwargs.kwargs["delay_until"] == "2025-01-15T10:00:00Z"


def test_enqueue_batch_basic() -> None:
    """enqueue_batch() should create JobRequest objects and batch-enqueue."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_client.enqueue_batch.return_value = [MagicMock(spec=ojs.Job)]

    with patch("ojs_django.backend.get_client", return_value=mock_client):
        result = enqueue_batch([
            {"type": "email.send", "args": ["a@b.com", "welcome"]},
            {"type": "email.send", "args": ["c@d.com", "welcome"], "queue": "bulk"},
        ])

    mock_client.enqueue_batch.assert_called_once()
    requests = mock_client.enqueue_batch.call_args[0][0]
    assert len(requests) == 2
    assert requests[0].type == "email.send"
    assert requests[1].queue == "bulk"
