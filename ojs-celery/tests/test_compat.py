"""Tests for CeleryCompat class and task conversion."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ojs_celery.adapter import OJSTask
from ojs_celery.compat import CeleryCompat


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.enqueue.return_value = MagicMock(id="compat-job-id", type="test", state="available")
    return client


@pytest.fixture
def compat(mock_client: MagicMock) -> CeleryCompat:
    app = CeleryCompat(ojs_url="http://localhost:8080", default_queue="jobs")
    app._client = mock_client
    return app


class TestCeleryCompatTaskDecorator:
    """Tests for CeleryCompat.task() decorator."""

    def test_task_decorator_creates_task(self, compat: CeleryCompat) -> None:
        @compat.task(name="email.send")
        def send_email(to: str) -> None:
            pass

        assert isinstance(send_email, OJSTask)
        assert send_email.name == "email.send"

    def test_task_registered_in_compat(self, compat: CeleryCompat) -> None:
        @compat.task(name="email.send")
        def send_email(to: str) -> None:
            pass

        assert "email.send" in compat.tasks

    def test_task_without_parentheses(self, compat: CeleryCompat) -> None:
        @compat.task
        def my_task() -> None:
            pass

        assert isinstance(my_task, OJSTask)

    def test_task_default_name(self, compat: CeleryCompat) -> None:
        @compat.task()
        def my_task() -> None:
            pass

        assert my_task.name.endswith("my_task")

    def test_task_bind_accepted(self, compat: CeleryCompat) -> None:
        """bind parameter is accepted for Celery compat (ignored)."""

        @compat.task(name="test.task", bind=True)
        def bound_task() -> None:
            pass

        assert isinstance(bound_task, OJSTask)

    def test_task_max_retries_accepted(self, compat: CeleryCompat) -> None:
        """max_retries parameter is accepted for Celery compat."""

        @compat.task(name="test.task", max_retries=5)
        def retryable_task() -> None:
            pass

        assert isinstance(retryable_task, OJSTask)

    def test_task_direct_call(self, compat: CeleryCompat) -> None:
        @compat.task(name="math.add")
        def add(a: int, b: int) -> int:
            return a + b

        assert add(2, 3) == 5


class TestCeleryCompatDelay:
    """Tests for task.delay() via CeleryCompat."""

    def test_delay_uses_default_queue(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        @compat.task(name="email.send")
        def send_email(to: str) -> None:
            pass

        send_email.delay("user@example.com")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="jobs"
        )

    def test_delay_with_task_specific_queue(
        self, compat: CeleryCompat, mock_client: MagicMock
    ) -> None:
        @compat.task(name="email.send", queue="email")
        def send_email(to: str) -> None:
            pass

        send_email.delay("user@example.com")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="email"
        )


class TestCeleryCompatSendTask:
    """Tests for CeleryCompat.send_task() dynamic dispatch."""

    def test_send_task_basic(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task("email.send", args=["user@example.com"])
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="jobs"
        )

    def test_send_task_with_queue(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task("email.send", args=["user@example.com"], queue="email")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"], queue="email"
        )

    def test_send_task_with_kwargs(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task(
            "email.send",
            args=["user@example.com"],
            kwargs={"priority": "high"},
        )
        mock_client.enqueue.assert_called_once_with(
            "email.send",
            ["user@example.com"],
            queue="jobs",
            meta={"kwargs": {"priority": "high"}},
        )

    def test_send_task_with_countdown(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task("email.send", args=[], countdown=60)
        call_kwargs = mock_client.enqueue.call_args[1]
        assert "delay_until" in call_kwargs

    def test_send_task_with_meta(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task("email.send", args=[], meta={"tenant": "acme"})
        mock_client.enqueue.assert_called_once_with(
            "email.send", [], queue="jobs", meta={"tenant": "acme"}
        )

    def test_send_task_no_args(self, compat: CeleryCompat, mock_client: MagicMock) -> None:
        compat.send_task("cleanup.run")
        mock_client.enqueue.assert_called_once_with("cleanup.run", [], queue="jobs")


class TestCeleryCompatLifecycle:
    """Tests for CeleryCompat lifecycle management."""

    def test_lazy_client_initialization(self) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080")
        assert compat._client is None

    def test_close(self, mock_client: MagicMock) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080")
        compat._client = mock_client
        compat.close()
        mock_client.close.assert_called_once()
        assert compat._client is None

    def test_close_when_no_client(self) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080")
        compat.close()  # should not raise

    def test_default_queue(self) -> None:
        compat = CeleryCompat(ojs_url="http://localhost:8080", default_queue="high")
        assert compat.default_queue == "high"
