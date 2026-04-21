"""Tests for the @ojs.job() decorator."""

from __future__ import annotations

import pytest
from flask import Flask

from ojs_flask import OJS


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestJobDecorator:
    """Tests for the OJS.job() decorator and handler registry."""

    def test_register_job_handler(self, app: Flask) -> None:
        """A decorated function should be registered as a handler."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        assert "email.send" in ext._handlers
        assert ext._handlers["email.send"] is handle_email

    def test_register_multiple_handlers(self, app: Flask) -> None:
        """Multiple handlers for different job types can be registered."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        @ext.job("report.generate")
        def handle_report(ctx):  # type: ignore[no-untyped-def]
            pass

        assert len(ext._handlers) == 2
        assert ext._handlers["email.send"] is handle_email
        assert ext._handlers["report.generate"] is handle_report

    def test_registered_types(self, app: Flask) -> None:
        """registered_types property should list all registered job types."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        @ext.job("report.generate")
        def handle_report(ctx):  # type: ignore[no-untyped-def]
            pass

        types = ext.registered_types
        assert "email.send" in types
        assert "report.generate" in types
        assert len(types) == 2

    def test_get_handler(self, app: Flask) -> None:
        """get_handler should return the registered handler for a job type."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        handler = ext.get_handler("email.send")
        assert handler is handle_email

    def test_get_handler_unknown_returns_none(self, app: Flask) -> None:
        """get_handler should return None for an unknown job type."""
        ext = OJS(app)
        assert ext.get_handler("nonexistent.job") is None

    def test_decorator_preserves_function(self, app: Flask) -> None:
        """The decorator should return the original function unchanged."""
        ext = OJS(app)

        def original_handler(ctx):  # type: ignore[no-untyped-def]
            return "result"

        decorated = ext.job("email.send")(original_handler)
        assert decorated is original_handler
        assert decorated(None) == "result"

    def test_handler_with_queue(self, app: Flask) -> None:
        """A handler registered with a queue should store queue metadata."""
        ext = OJS(app)

        @ext.job("report.generate", queue="reports")
        def handle_report(ctx):  # type: ignore[no-untyped-def]
            pass

        handler = ext.get_handler("report.generate")
        assert handler is not None
        assert handler._ojs_queue == "reports"  # type: ignore[attr-defined]

    def test_handler_without_queue_has_none(self, app: Flask) -> None:
        """A handler registered without a queue should have _ojs_queue = None."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        handler = ext.get_handler("email.send")
        assert handler is not None
        assert handler._ojs_queue is None  # type: ignore[attr-defined]

    def test_registered_types_empty_by_default(self) -> None:
        """An extension with no handlers should have an empty registered_types."""
        ext = OJS()
        assert ext.registered_types == []

    def test_handler_stores_job_type_metadata(self, app: Flask) -> None:
        """The decorator should attach _ojs_job_type to the handler."""
        ext = OJS(app)

        @ext.job("email.send")
        def handle_email(ctx):  # type: ignore[no-untyped-def]
            pass

        assert handle_email._ojs_job_type == "email.send"  # type: ignore[attr-defined]
