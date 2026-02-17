"""Tests for the ojs_worker management command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command, get_commands


def test_ojs_worker_command_is_discovered() -> None:
    """The ojs_worker command should be registered by Django."""
    commands = get_commands()
    assert "ojs_worker" in commands


def test_ojs_worker_command_help() -> None:
    """The ojs_worker command should have meaningful help text."""
    out = StringIO()
    with patch("sys.stdout", out):
        try:
            call_command("ojs_worker", "--help")
        except SystemExit:
            pass  # --help causes SystemExit(0)
    output = out.getvalue()
    assert "OJS" in output or "worker" in output.lower()
