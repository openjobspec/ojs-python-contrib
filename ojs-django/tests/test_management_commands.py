"""Tests for OJS management commands."""

from __future__ import annotations

import contextlib
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command, get_commands

from ojs_django.conf import reset_settings


def test_ojs_worker_command_is_discovered() -> None:
    """The ojs_worker command should be registered by Django."""
    commands = get_commands()
    assert "ojs_worker" in commands


def test_ojs_status_command_is_discovered() -> None:
    """The ojs_status command should be registered by Django."""
    commands = get_commands()
    assert "ojs_status" in commands


def test_ojs_purge_command_is_discovered() -> None:
    """The ojs_purge command should be registered by Django."""
    commands = get_commands()
    assert "ojs_purge" in commands


def test_ojs_worker_command_help() -> None:
    """The ojs_worker command should have meaningful help text."""
    out = StringIO()
    with patch("sys.stdout", out), contextlib.suppress(SystemExit):
        call_command("ojs_worker", "--help")
    output = out.getvalue()
    assert "OJS" in output or "worker" in output.lower()


def test_ojs_status_healthy_server() -> None:
    """ojs_status should display health information."""
    reset_settings()
    mock_client = MagicMock()
    mock_client.health.return_value = {"status": "ok"}
    mock_client.list_queues.return_value = []

    out = StringIO()
    with patch("ojs_django.management.commands.ojs_status.get_client", return_value=mock_client):
        call_command("ojs_status", stdout=out)

    output = out.getvalue()
    assert "ok" in output


def test_ojs_status_unreachable_server() -> None:
    """ojs_status should handle connection errors gracefully."""
    reset_settings()
    mock_client = MagicMock()
    mock_client.health.side_effect = ConnectionError("refused")

    err = StringIO()
    with patch("ojs_django.management.commands.ojs_status.get_client", return_value=mock_client):
        call_command("ojs_status", stderr=err)

    output = err.getvalue()
    assert "Cannot connect" in output


def test_ojs_status_json_output() -> None:
    """ojs_status --json should produce JSON."""
    import json

    reset_settings()
    mock_client = MagicMock()
    mock_client.health.return_value = {"status": "ok"}
    mock_client.list_queues.return_value = []

    out = StringIO()
    with patch("ojs_django.management.commands.ojs_status.get_client", return_value=mock_client):
        call_command("ojs_status", "--json", stdout=out)

    data = json.loads(out.getvalue())
    assert data["health"]["status"] == "ok"


def test_ojs_purge_no_jobs() -> None:
    """ojs_purge should handle empty dead letter queue."""
    reset_settings()
    mock_client = MagicMock()
    mock_client.list_dead_letter_jobs.return_value = {"jobs": []}

    out = StringIO()
    with patch("ojs_django.management.commands.ojs_purge.get_client", return_value=mock_client):
        call_command("ojs_purge", stdout=out)

    assert "No dead letter jobs" in out.getvalue()


def test_ojs_purge_dry_run() -> None:
    """ojs_purge --dry-run should not delete anything."""
    reset_settings()
    mock_client = MagicMock()
    mock_client.list_dead_letter_jobs.return_value = {
        "jobs": [{"id": "job-1", "type": "email.send"}]
    }

    out = StringIO()
    with patch("ojs_django.management.commands.ojs_purge.get_client", return_value=mock_client):
        call_command("ojs_purge", "--dry-run", stdout=out)

    output = out.getvalue()
    assert "Dry run" in output
    assert "Would delete" in output
    mock_client.delete_dead_letter_job.assert_not_called()


def test_ojs_purge_deletes_jobs() -> None:
    """ojs_purge should delete dead letter jobs."""
    reset_settings()
    mock_client = MagicMock()
    mock_client.list_dead_letter_jobs.return_value = {
        "jobs": [{"id": "job-1", "type": "test"}, {"id": "job-2", "type": "test"}]
    }
    mock_client.delete_dead_letter_job.return_value = {}

    out = StringIO()
    with patch("ojs_django.management.commands.ojs_purge.get_client", return_value=mock_client):
        call_command("ojs_purge", stdout=out)

    assert "Deleted 2" in out.getvalue()
    assert mock_client.delete_dead_letter_job.call_count == 2
