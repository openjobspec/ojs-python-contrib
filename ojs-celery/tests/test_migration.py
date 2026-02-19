"""Tests for Celery migration helpers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ojs_celery.adapter import OJSAdapter, OJSTask
from ojs_celery.migration import migrate_task


class TestMigrateTask:
    """Tests for wrapping Celery tasks as OJS tasks."""

    def test_migrate_basic_task(self) -> None:
        celery_task = MagicMock()
        celery_task.name = "email.send"
        celery_task.run = lambda to, body: f"sent to {to}"

        ojs_task = migrate_task(celery_task)
        assert isinstance(ojs_task, OJSTask)
        assert ojs_task.name == "email.send"

    def test_migrate_task_preserves_function(self) -> None:
        def send_email(to: str, body: str) -> str:
            return f"sent to {to}"

        celery_task = MagicMock()
        celery_task.name = "email.send"
        celery_task.run = send_email

        ojs_task = migrate_task(celery_task)
        result = ojs_task("user@example.com", "Hello")
        assert result == "sent to user@example.com"

    def test_migrate_task_with_adapter(self) -> None:
        adapter = OJSAdapter(ojs_url="http://localhost:8080")
        mock_client = MagicMock()
        mock_client.enqueue.return_value = MagicMock(id="test-id")
        adapter._client = mock_client

        celery_task = MagicMock()
        celery_task.name = "email.send"
        celery_task.run = lambda: None

        ojs_task = migrate_task(celery_task, adapter=adapter)
        ojs_task.delay("user@example.com")
        mock_client.enqueue.assert_called_once_with(
            "email.send", ["user@example.com"]
        )

    def test_migrate_task_without_run_attribute(self) -> None:
        """If the task doesn't have .run, use the task object itself."""
        celery_task = MagicMock()
        celery_task.name = "email.send"
        del celery_task.run  # remove .run attribute

        ojs_task = migrate_task(celery_task)
        assert ojs_task.name == "email.send"
        assert ojs_task.fn is celery_task

    def test_migrate_task_creates_adapter_with_url(self) -> None:
        celery_task = MagicMock()
        celery_task.name = "email.send"
        celery_task.run = lambda: None

        ojs_task = migrate_task(celery_task, ojs_url="http://custom:9090")
        assert ojs_task._adapter.ojs_url == "http://custom:9090"
