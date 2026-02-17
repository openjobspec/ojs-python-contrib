"""Flask extension for Open Job Spec (OJS)."""

from __future__ import annotations

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
    """

    def __init__(self, app: Flask | None = None) -> None:
        self._app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize the extension with a Flask application.

        Reads the following configuration keys:

        * ``OJS_URL`` – OJS server base URL (default ``http://localhost:8080``)
        * ``OJS_QUEUES`` – list of queue names for workers (default ``["default"]``)
        """
        app.config.setdefault("OJS_URL", "http://localhost:8080")
        app.config.setdefault("OJS_QUEUES", ["default"])

        client = ojs.SyncClient(app.config["OJS_URL"])
        app.extensions["ojs"] = client
        app.teardown_appcontext(self._teardown)

    @staticmethod
    def _teardown(exc: BaseException | None) -> None:  # noqa: ARG004
        """Teardown callback registered on the app context."""

    @property
    def client(self) -> ojs.SyncClient:
        """Return the :class:`ojs.SyncClient` stored on the current app."""
        from flask import current_app

        try:
            return current_app.extensions["ojs"]  # type: ignore[return-value]
        except KeyError:
            raise RuntimeError(
                "OJS extension not initialized. "
                "Call OJS(app) or OJS.init_app(app) first."
            ) from None

    def enqueue(self, job_type: str, args: list[Any] | None = None, **kwargs: Any) -> ojs.Job:
        """Convenience method to enqueue a job via the current app client."""
        return self.client.enqueue(job_type, args, **kwargs)
