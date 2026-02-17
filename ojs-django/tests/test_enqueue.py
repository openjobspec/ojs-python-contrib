"""Tests for enqueue and enqueue_after_commit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import ojs

from ojs_django.enqueue import enqueue_after_commit


@pytest.fixture(autouse=True)
def _reset_client() -> None:  # type: ignore[misc]
    """Reset the module-level cached client between tests."""
    import ojs_django.enqueue as mod

    mod._sync_client = None


@pytest.mark.django_db(transaction=True)
def test_enqueue_after_commit_defers_until_commit() -> None:
    """Job enqueue should only happen when the transaction commits."""
    mock_client = MagicMock(spec=ojs.SyncClient)
    mock_client.enqueue.return_value = MagicMock(spec=ojs.Job)

    with patch("ojs_django.enqueue.get_client", return_value=mock_client):
        with transaction.atomic():
            enqueue_after_commit("email.send", ["user@test.com"], queue="email")
            # Not yet called inside the transaction
            mock_client.enqueue.assert_not_called()

        # Called after the transaction committed
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

    with patch("ojs_django.enqueue.get_client", return_value=mock_client):
        try:
            with transaction.atomic():
                enqueue_after_commit("email.send", ["user@test.com"])
                raise ValueError("force rollback")
        except ValueError:
            pass

        mock_client.enqueue.assert_not_called()
