"""Tests for Celery retry behavior and countdown-to-delay_until conversion."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from ojs_celery.adapter import OJSAdapter
from ojs_celery.compat import CeleryCompat


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.enqueue.return_value = MagicMock(id="test-id", type="test", state="available")
    return client


@pytest.fixture
def adapter(mock_client: MagicMock) -> OJSAdapter:
    a = OJSAdapter(ojs_url="http://localhost:8080")
    a._client = mock_client
    return a


class TestCountdownConversion:
    """Tests for countdown parameter converting to delay_until."""

    def test_countdown_sets_delay_until(self, adapter: OJSAdapter, mock_client: MagicMock) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        before = datetime.datetime.now(datetime.UTC)
        send_email.apply_async(args=["user@example.com"], countdown=120)
        after = datetime.datetime.now(datetime.UTC)

        call_kwargs = mock_client.enqueue.call_args[1]
        delay_until = datetime.datetime.fromisoformat(call_kwargs["delay_until"])
        expected_min = before + datetime.timedelta(seconds=120)
        expected_max = after + datetime.timedelta(seconds=120)
        assert expected_min <= delay_until <= expected_max

    def test_countdown_zero(self, adapter: OJSAdapter, mock_client: MagicMock) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=[], countdown=0)
        call_kwargs = mock_client.enqueue.call_args[1]
        assert "delay_until" in call_kwargs

    def test_no_countdown_no_delay_until(self, adapter: OJSAdapter, mock_client: MagicMock) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=["user@example.com"])
        call_kwargs = mock_client.enqueue.call_args
        assert "delay_until" not in call_kwargs[1]


class TestCeleryCompatRetry:
    """Tests for retry behavior via CeleryCompat."""

    def test_compat_countdown_sets_delay_until(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080")
        compat._client = mock_client

        @compat.task(name="flaky.task", max_retries=3)
        def flaky_task() -> None:
            pass

        flaky_task.apply_async(args=[1], countdown=60)
        call_kwargs = mock_client.enqueue.call_args[1]
        assert "delay_until" in call_kwargs

    def test_send_task_countdown(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080")
        compat._client = mock_client

        compat.send_task("retry.task", args=[1], countdown=300)
        call_kwargs = mock_client.enqueue.call_args[1]
        delay_until = datetime.datetime.fromisoformat(call_kwargs["delay_until"])
        # Should be approximately 300 seconds in the future
        now = datetime.datetime.now(datetime.UTC)
        diff = (delay_until - now).total_seconds()
        assert 295 <= diff <= 305


class TestCombinedMetaAndKwargs:
    """Tests for combining meta and kwargs in apply_async."""

    def test_kwargs_merged_into_meta(self, adapter: OJSAdapter, mock_client: MagicMock) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(
            args=[],
            kwargs={"priority": "high"},
            meta={"source": "api"},
        )
        call_kwargs = mock_client.enqueue.call_args[1]
        assert call_kwargs["meta"]["kwargs"] == {"priority": "high"}
        assert call_kwargs["meta"]["source"] == "api"

    def test_only_kwargs_creates_meta(self, adapter: OJSAdapter, mock_client: MagicMock) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=[], kwargs={"key": "value"})
        call_kwargs = mock_client.enqueue.call_args[1]
        assert call_kwargs["meta"] == {"kwargs": {"key": "value"}}
