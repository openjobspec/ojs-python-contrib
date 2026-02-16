"""Tests for the OJS Celery adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ojs_celery.adapter import OJSAdapter, OJSTask, ojs_task


@dataclass
class FakeJob:
    """Minimal fake OJS Job for testing."""

    id: str = "test-job-id"
    type: str = "test.task"
    state: str = "available"


@pytest.fixture()
def mock_client() -> MagicMock:
    """Create a mock OJS SyncClient."""
    client = MagicMock()
    client.enqueue.return_value = FakeJob()
    return client


@pytest.fixture()
def adapter(mock_client: MagicMock) -> OJSAdapter:
    """Create an OJSAdapter with a mocked client."""
    a = OJSAdapter(ojs_url="http://localhost:8080")
    a._client = mock_client
    return a


class TestOJSTask:
    """Tests for OJSTask created by adapter.task()."""

    def test_task_decorator_creates_ojs_task(self, adapter: OJSAdapter) -> None:
        @adapter.task(name="email.send")
        def send_email(to: str, body: str) -> None:
            pass

        assert isinstance(send_email, OJSTask)
        assert send_email.name == "email.send"

    def test_task_registered_in_adapter(self, adapter: OJSAdapter) -> None:
        @adapter.task(name="email.send")
        def send_email(to: str, body: str) -> None:
            pass

        assert "email.send" in adapter.tasks
        assert adapter.tasks["email.send"] is send_email

    def test_task_default_name_from_function(self, adapter: OJSAdapter) -> None:
        @adapter.task()
        def my_function() -> None:
            pass

        expected_suffix = "test_adapter.TestOJSTask.test_task_default_name_from_function.<locals>.my_function"
        assert my_function.name.endswith(expected_suffix)

    def test_task_direct_call(self, adapter: OJSAdapter) -> None:
        @adapter.task(name="math.add")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5


class TestDelay:
    """Tests for OJSTask.delay()."""

    def test_delay_calls_enqueue(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="email.send")
        def send_email(to: str, subject: str) -> None:
            pass

        result = send_email.delay("user@example.com", "Hello")

        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com", "Hello"]
        )
        assert result.id == "test-job-id"

    def test_delay_no_args(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="cleanup.run")
        def run_cleanup() -> None:
            pass

        run_cleanup.delay()
        mock_client.enqueue.assert_called_once_with("cleanup.run", [])


class TestApplyAsync:
    """Tests for OJSTask.apply_async()."""

    def test_apply_async_with_args(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="report.generate")
        def generate_report(report_id: int) -> None:
            pass

        generate_report.apply_async(args=[42])
        mock_client.enqueue.assert_called_once_with("report.generate", [42])

    def test_apply_async_with_queue(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="report.generate")
        def generate_report(report_id: int) -> None:
            pass

        generate_report.apply_async(args=[42], queue="reports")
        mock_client.enqueue.assert_called_once_with(
            "report.generate", [42], queue="reports"
        )

    def test_apply_async_with_kwargs_in_meta(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(
            args=["user@example.com"],
            kwargs={"priority": "high"},
        )
        mock_client.enqueue.assert_called_once_with(
            "email.send",
            ["user@example.com"],
            meta={"kwargs": {"priority": "high"}},
        )

    def test_apply_async_with_countdown(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=["user@example.com"], countdown=300)

        call_kwargs = mock_client.enqueue.call_args
        assert call_kwargs[0] == ("email.send", ["user@example.com"])
        assert "delay_until" in call_kwargs[1]

    def test_apply_async_with_meta(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="email.send")
        def send_email() -> None:
            pass

        send_email.apply_async(args=[], meta={"source": "api"})
        mock_client.enqueue.assert_called_once_with(
            "email.send", [], meta={"source": "api"}
        )

    def test_apply_async_empty_args(
        self, adapter: OJSAdapter, mock_client: MagicMock
    ) -> None:
        @adapter.task(name="cleanup.run")
        def run_cleanup() -> None:
            pass

        run_cleanup.apply_async()
        mock_client.enqueue.assert_called_once_with("cleanup.run", [])


class TestModuleLevelDecorator:
    """Tests for the module-level ojs_task decorator."""

    def test_ojs_task_creates_task(self) -> None:
        with patch("ojs_celery.adapter.ojs.SyncClient") as mock_cls:
            mock_cls.return_value.enqueue.return_value = FakeJob()

            @ojs_task(name="test.task", ojs_url="http://test:8080")
            def my_task(x: int) -> None:
                pass

            assert isinstance(my_task, OJSTask)
            assert my_task.name == "test.task"


class TestAdapterLifecycle:
    """Tests for adapter creation and cleanup."""

    def test_adapter_lazy_client(self) -> None:
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        assert adapter._client is None

    def test_adapter_close(self, mock_client: MagicMock) -> None:
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter._client = mock_client
        adapter.close()
        mock_client.close.assert_called_once()
        assert adapter._client is None

    def test_adapter_close_when_no_client(self) -> None:
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        adapter.close()  # Should not raise
