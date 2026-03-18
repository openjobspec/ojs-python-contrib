"""Tests for the OJS Flask CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from ojs_flask import OJS


@pytest.fixture()
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    OJS(app)
    return app


@pytest.fixture()
def runner(app: Flask) -> FlaskCliRunner:
    return app.test_cli_runner()


class TestCLICommandRegistration:
    """Tests that CLI commands are registered correctly."""

    def test_worker_command_exists(self, runner: FlaskCliRunner) -> None:
        """The 'ojs worker' command should be registered."""
        result = runner.invoke(args=["ojs", "worker", "--help"])
        assert result.exit_code == 0
        assert "Start an OJS worker" in result.output

    def test_status_command_exists(self, runner: FlaskCliRunner) -> None:
        """The 'ojs status' command should be registered."""
        result = runner.invoke(args=["ojs", "status", "--help"])
        assert result.exit_code == 0
        assert "Show OJS server" in result.output

    def test_cron_command_exists(self, runner: FlaskCliRunner) -> None:
        """The 'ojs cron' command should be registered."""
        result = runner.invoke(args=["ojs", "cron", "--help"])
        assert result.exit_code == 0
        assert "Register a cron job" in result.output

    def test_ojs_group_help(self, runner: FlaskCliRunner) -> None:
        """The 'ojs' group should show help with subcommands."""
        result = runner.invoke(args=["ojs", "--help"])
        assert result.exit_code == 0
        assert "worker" in result.output
        assert "status" in result.output
        assert "cron" in result.output


class TestWorkerCommand:
    """Tests for the 'ojs worker' CLI command."""

    @patch("ojs_flask.cli.FlaskOJSWorker")
    def test_worker_command_uses_config_defaults(
        self, mock_worker_cls: MagicMock, runner: FlaskCliRunner, app: Flask
    ) -> None:
        """Worker command should use app config defaults when no options given."""
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker

        # Simulate immediate KeyboardInterrupt to avoid blocking
        with patch("signal.pause", side_effect=KeyboardInterrupt):
            result = runner.invoke(args=["ojs", "worker"])

        mock_worker.start.assert_called_once()
        call_kwargs = mock_worker.start.call_args
        assert call_kwargs.kwargs["concurrency"] == 10
        assert call_kwargs.kwargs["poll_interval"] == 2.0

    @patch("ojs_flask.cli.FlaskOJSWorker")
    def test_worker_command_custom_options(
        self, mock_worker_cls: MagicMock, runner: FlaskCliRunner
    ) -> None:
        """Worker command should pass custom CLI options to the worker."""
        mock_worker = MagicMock()
        mock_worker_cls.return_value = mock_worker

        with patch("signal.pause", side_effect=KeyboardInterrupt):
            result = runner.invoke(
                args=["ojs", "worker", "--queues", "email,reports", "--concurrency", "5"]
            )

        call_kwargs = mock_worker.start.call_args
        assert call_kwargs.kwargs["queues"] == ["email", "reports"]
        assert call_kwargs.kwargs["concurrency"] == 5


class TestCronCommand:
    """Tests for the 'ojs cron' CLI command."""

    @patch("ojs_flask.cli.get_client")
    def test_cron_command_with_options(
        self, mock_get_client: MagicMock, runner: FlaskCliRunner
    ) -> None:
        """Cron command should enqueue a cron job with the given schedule."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(
            args=["ojs", "cron", "report.daily", "0 9 * * *", "--queue", "reports"]
        )

        assert result.exit_code == 0
        mock_client.enqueue.assert_called_once_with(
            "report.daily", [], queue="reports", cron="0 9 * * *"
        )
        assert "Cron job registered" in result.output

    @patch("ojs_flask.cli.get_client")
    def test_cron_command_default_queue(
        self, mock_get_client: MagicMock, runner: FlaskCliRunner
    ) -> None:
        """Cron command should default to the 'default' queue."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        result = runner.invoke(args=["ojs", "cron", "cleanup.run", "*/5 * * * *"])

        assert result.exit_code == 0
        mock_client.enqueue.assert_called_once_with(
            "cleanup.run", [], queue="default", cron="*/5 * * * *"
        )

    @patch("ojs_flask.cli.get_client")
    def test_cron_command_failure(
        self, mock_get_client: MagicMock, runner: FlaskCliRunner
    ) -> None:
        """Cron command should report errors on failure."""
        mock_client = MagicMock()
        mock_client.enqueue.side_effect = ConnectionError("Connection refused")
        mock_get_client.return_value = mock_client

        result = runner.invoke(args=["ojs", "cron", "fail.job", "* * * * *"])

        assert result.exit_code != 0
        assert "Failed to register cron job" in result.output
