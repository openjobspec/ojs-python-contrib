"""Flask extension for Open Job Spec (OJS)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import ojs
from flask import Flask


class OJS:
    """Flask extension that manages an OJS SyncClient bound to the application.

    Supports both direct initialization and the ``init_app`` factory pattern::

        # Direct
        ext = OJS(app)

        # Factory
        ext = OJS()
        ext.init_app(app)

    Job handlers can be registered with the :meth:`job` decorator::

        ojs_ext = OJS()

        @ojs_ext.job("email.send")
        def handle_email(ctx):
            send_mail(ctx.args[0])
    """

    def __init__(self, app: Flask | None = None) -> None:
        self._app = app
        self._handlers: dict[str, Callable[..., Any]] = {}
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the extension with a Flask application.

        Reads the following configuration keys:

        * ``OJS_URL`` - OJS server base URL (default ``http://localhost:8080``)
        * ``OJS_QUEUES`` - list of queue names for workers (default ``["default"]``)
        * ``OJS_CONCURRENCY`` - default worker concurrency (default ``10``)
        * ``OJS_POLL_INTERVAL`` - default worker poll interval in seconds (default ``2.0``)

        Also registers the ``flask ojs`` CLI command group.
        """
        app.config.setdefault("OJS_URL", "http://localhost:8080")
        app.config.setdefault("OJS_QUEUES", ["default"])
        app.config.setdefault("OJS_CONCURRENCY", 10)
        app.config.setdefault("OJS_POLL_INTERVAL", 2.0)

        client = ojs.SyncClient(app.config["OJS_URL"])
        app.extensions["ojs"] = client
        app.extensions["ojs_extension"] = self
        app.teardown_appcontext(self._teardown)

        from ojs_flask.cli import ojs_cli

        app.cli.add_command(ojs_cli)

    @staticmethod
    def _teardown(exc: BaseException | None) -> None:
        """Teardown callback registered on the app context."""

    @property
    def client(self) -> ojs.SyncClient:
        """Return the :class:`ojs.SyncClient` stored on the current app."""
        from ojs_flask.helpers import get_client

        return get_client()

    def enqueue(self, job_type: str, args: list[Any] | None = None, **kwargs: Any) -> ojs.Job:
        """Convenience method to enqueue a job via the current app client."""
        return self.client.enqueue(job_type, args, **kwargs)

    def job(self, job_type: str, *, queue: str | None = None) -> Callable[..., Any]:
        """Decorator to register a function as a handler for the given job type.

        Args:
            job_type: The job type identifier (e.g. ``"email.send"``).
            queue: Optional queue name override. Stored as metadata on the
                handler for the worker to use when subscribing to queues.

        Returns:
            A decorator that registers the function and returns it unchanged.

        Example::

            @ojs_ext.job("email.send")
            def handle_email(ctx):
                send_mail(ctx.args[0])

            @ojs_ext.job("report.generate", queue="reports")
            def handle_report(ctx):
                build_report(ctx.args[0])
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            fn._ojs_job_type = job_type  # type: ignore[attr-defined]
            fn._ojs_queue = queue  # type: ignore[attr-defined]
            self._handlers[job_type] = fn
            return fn

        return decorator

    @property
    def registered_types(self) -> list[str]:
        """Return a list of all registered job type names."""
        return list(self._handlers.keys())

    def get_handler(self, job_type: str) -> Callable[..., Any] | None:
        """Retrieve the handler function registered for the given job type.

        Args:
            job_type: The job type identifier.

        Returns:
            The handler callable, or ``None`` if no handler is registered.
        """
        return self._handlers.get(job_type)
