"""Tests for Celery-to-OJS task conversion and priority mapping."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ojs_celery.adapter import OJSAdapter, OJSTask
from ojs_celery.compat import CeleryCompat


@pytest.fixture()
def mock_client() -> MagicMock:
    client = MagicMock()
    client.enqueue.return_value = MagicMock(id="test-id", type="test", state="available")
    return client


class TestTaskConversion:
    """Tests for converting between OJS and Celery task representations."""

    def test_adapter_task_delay_maps_args(self, mock_client: MagicMock) -> None:
        """Celery delay(*args) should map to OJS enqueue(type, [args])."""
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client

        @adapter.task(name="email.send")
        def send_email(to: str, subject: str, body: str) -> None:
            pass

        send_email.delay("user@example.com", "Hello", "Body")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com", "Hello", "Body"]
        )

    def test_adapter_apply_async_maps_queue(self, mock_client: MagicMock) -> None:
        """Celery apply_async(queue=...) should map to OJS queue parameter."""
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client

        @adapter.task(name="report.generate")
        def gen_report(report_id: int) -> None:
            pass

        gen_report.apply_async(args=[42], queue="reports")
        mock_client.enqueue.assert_called_once_with(
            "report.generate", [42], queue="reports"
        )

    def test_celery_kwargs_stored_in_meta(self, mock_client: MagicMock) -> None:
        """Celery kwargs should be stored in OJS meta under 'kwargs' key."""
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client

        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(
            args=["user@example.com"],
            kwargs={"template": "welcome", "lang": "en"},
        )
        call_kwargs = mock_client.enqueue.call_args[1]
        assert call_kwargs["meta"]["kwargs"] == {"template": "welcome", "lang": "en"}


class TestQueueMapping:
    """Tests for queue mapping between Celery and OJS."""

    def test_compat_default_queue(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080", default_queue="celery")
        compat._client = mock_client

        compat.send_task("email.send", args=["user@example.com"])
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="celery"
        )

    def test_compat_override_queue(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080", default_queue="celery")
        compat._client = mock_client

        compat.send_task("email.send", args=[], queue="priority")
        mock_client.enqueue.assert_called_once_with(
            "email.send", [], queue="priority"
        )

    def test_task_specific_queue_on_compat(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080", default_queue="default")
        compat._client = mock_client

        @compat.task(name="email.send", queue="email")
        def send_email(to: str) -> None:
            pass

        send_email.delay("user@example.com")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="email"
        )


class TestPriorityMapping:
    """Tests for priority handling in task conversion."""

    def test_adapter_no_priority_by_default(self, mock_client: MagicMock) -> None:
        """By default, no priority is sent to OJS."""
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client

        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.delay()
        call_args = mock_client.enqueue.call_args
        # delay() calls enqueue(name, args) with no priority kwarg
        assert call_args == (("email.send", []),)

    def test_meta_can_carry_priority(self, mock_client: MagicMock) -> None:
        """Priority can be passed via meta for custom handling."""
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client

        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=[], meta={"priority": 10})
        call_kwargs = mock_client.enqueue.call_args[1]
        assert call_kwargs["meta"]["priority"] == 10

