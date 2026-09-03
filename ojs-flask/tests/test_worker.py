"""Tests for the FlaskOJSWorker lifecycle manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ojs_flask import OJS
from ojs_flask.worker import FlaskOJSWorker


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["OJS_URL"] = "http://localhost:8080"
    app.config["OJS_QUEUES"] = ["default"]
    return app


@pytest.fixture
def ojs_ext(app: Flask) -> OJS:
    ext = OJS(app)

    @ext.job("email.send")
    def handle_email(ctx):  # type: ignore[no-untyped-def]
        pass

    return ext


class TestWorkerInitialState:
    """Tests for the FlaskOJSWorker initial state."""

    def test_worker_not_running_initially(self, app: Flask) -> None:
        """A newly created worker should not be running."""
        worker = FlaskOJSWorker(app=app)
        assert worker.is_running is False

    def test_worker_attributes_initialized(self, app: Flask) -> None:
        """Worker should initialize with None thread and loop."""
        worker = FlaskOJSWorker(app=app)
        assert worker._thread is None
        assert worker._loop is None
        assert worker._worker is None


class TestWorkerLifecycle:
    """Tests for starting and stopping the worker."""

    @patch("ojs_flask.worker._ojs_sdk.Worker")
    def test_worker_start_creates_thread(
        self, mock_worker_cls: MagicMock, app: Flask, ojs_ext: OJS
    ) -> None:
        """Starting the worker should create a background thread."""
        mock_worker_instance = MagicMock()
        # Make start() return a coroutine
        mock_worker_instance.start = MagicMock(return_value=_make_coro(None))
        mock_worker_cls.return_value = mock_worker_instance

        worker = FlaskOJSWorker(app=app, ojs_ext=ojs_ext)
        worker.start(queues=["default"], concurrency=5, poll_interval=1.0)

        try:
            # Worker should have a thread
            assert worker._thread is not None
            assert worker._thread.name == "ojs-worker"

            # OJS Worker should be created with correct args
            mock_worker_cls.assert_called_once_with(
                "http://localhost:8080",
                queues=["default"],
                concurrency=5,
                poll_interval=1.0,
            )

            # Registered handlers should be forwarded to the SDK worker
            mock_worker_instance.handler.assert_called_once_with(
                "email.send", ojs_ext._handlers["email.send"]
            )
        finally:
            worker.stop()

    @patch("ojs_flask.worker._ojs_sdk.Worker")
    def test_worker_stop(self, mock_worker_cls: MagicMock, app: Flask) -> None:
        """Stopping the worker should clean up the thread."""
        mock_worker_instance = MagicMock()
        mock_worker_instance.start = MagicMock(return_value=_make_coro(None))
        mock_worker_cls.return_value = mock_worker_instance

        worker = FlaskOJSWorker(app=app)
        worker.start(queues=["default"])

        # Give the thread a moment to start
        if worker._thread is not None:
            worker._thread.join(timeout=2)

        worker.stop()

        assert worker._thread is None
        assert worker._worker is None
        mock_worker_instance.stop.assert_called_once()

    def test_worker_stop_when_not_started(self, app: Flask) -> None:
        """Stopping a worker that was never started should be a no-op."""
        worker = FlaskOJSWorker(app=app)
        worker.stop()  # Should not raise
        assert worker.is_running is False

    @patch("ojs_flask.worker._ojs_sdk.Worker")
    def test_worker_uses_app_config(self, mock_worker_cls: MagicMock, app: Flask) -> None:
        """Worker should read queues from app config when not specified."""
        app.config["OJS_QUEUES"] = ["high", "low"]
        mock_worker_instance = MagicMock()
        mock_worker_instance.start = MagicMock(return_value=_make_coro(None))
        mock_worker_cls.return_value = mock_worker_instance

        worker = FlaskOJSWorker(app=app)
        worker.start()

        try:
            mock_worker_cls.assert_called_once_with(
                "http://localhost:8080",
                queues=["high", "low"],
                concurrency=10,
                poll_interval=2.0,
            )
        finally:
            worker.stop()


async def _make_coro(value):  # type: ignore[no-untyped-def]
    """Helper to create an awaitable for mocking async worker.start()."""
    return value
