"""Flask-integrated OJS Worker lifecycle management."""

from __future__ import annotations

import asyncio
import logging
import signal
import threading
from typing import Any

import ojs as _ojs_sdk

logger = logging.getLogger(__name__)


class FlaskOJSWorker:
    """Manages an OJS Worker lifecycle integrated with Flask.

    Runs the async OJS worker in a background thread, allowing
    Flask's sync request handling to continue normally.

    Args:
        app: The Flask application instance. Used to access configuration
            and push an application context into the worker thread.
        ojs_ext: The :class:`~ojs_flask.extension.OJS` extension instance.
            If provided, registered handlers are automatically attached
            to the worker.

    Example::

        from ojs_flask import OJS, FlaskOJSWorker

        ojs_ext = OJS(app)

        @ojs_ext.job("email.send")
        def handle_email(ctx):
            send_mail(ctx.args[0])

        worker = FlaskOJSWorker(app=app, ojs_ext=ojs_ext)
        worker.start(queues=["default"], concurrency=5)
    """

    def __init__(self, app: Any = None, ojs_ext: Any = None) -> None:
        self._app = app
        self._ojs_ext = ojs_ext
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._worker: Any = None  # ojs.Worker
        self._stop_event = threading.Event()

    def start(
        self,
        queues: list[str] | None = None,
        concurrency: int = 10,
        poll_interval: float = 2.0,
    ) -> None:
        """Start the worker in a background thread.

        Args:
            queues: List of queue names to subscribe to.
                Defaults to the ``OJS_QUEUES`` config value.
            concurrency: Maximum number of concurrent job handlers.
            poll_interval: Seconds between polling the OJS server for jobs.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("Worker is already running.")
            return

        if queues is None and self._app is not None:
            queues = self._app.config.get("OJS_QUEUES", ["default"])
        queues = queues or ["default"]

        url = "http://localhost:8080"
        if self._app is not None:
            url = self._app.config.get("OJS_URL", url)

        self._worker = _ojs_sdk.Worker(
            url,
            queues=queues,
            concurrency=concurrency,
            poll_interval=poll_interval,
        )

        # Register handlers from the extension
        if self._ojs_ext is not None and hasattr(self._ojs_ext, "_handlers"):
            for job_type, handler in self._ojs_ext._handlers.items():
                self._worker.register(job_type, handler)

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_worker,
            daemon=True,
            name="ojs-worker",
        )
        self._thread.start()
        logger.info(
            "OJS worker started (queues=%s, concurrency=%d, poll_interval=%.1f)",
            queues,
            concurrency,
            poll_interval,
        )

    def _run_worker(self) -> None:
        """Run the async worker in a new event loop on the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._worker.start())
        except Exception:
            logger.exception("OJS worker encountered an error")
        finally:
            self._loop.close()
            self._loop = None

    def stop(self) -> None:
        """Stop the worker gracefully.

        Signals the worker to shut down and waits for the background
        thread to exit (up to 10 seconds).
        """
        if self._worker is None:
            return

        self._stop_event.set()

        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._loop.stop)

        try:
            self._worker.stop()
        except Exception:
            logger.exception("Error stopping OJS worker")

        if self._thread is not None:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logger.warning("OJS worker thread did not shut down within timeout")

        self._thread = None
        self._worker = None
        logger.info("OJS worker stopped")

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the worker thread is alive."""
        return self._thread is not None and self._thread.is_alive()
