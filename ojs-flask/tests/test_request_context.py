"""Tests for Flask extension request context access."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ojs_flask import OJS, enqueue, get_client


@pytest.fixture()
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestRequestContext:
    """Tests for accessing OJS client within Flask request context."""

    def test_client_accessible_in_request(self, app: Flask) -> None:
        OJS(app)
        with app.test_request_context("/"):
            client = get_client()
            assert client is not None

    def test_enqueue_within_request_context(self, app: Flask) -> None:
        with patch("ojs_flask.extension.ojs.SyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            OJS(app)
            with app.test_request_context("/"):
                enqueue("email.send", ["user@example.com"])
                mock_client.enqueue.assert_called_once_with(
                    "email.send", ["user@example.com"]
                )

    def test_client_same_across_request(self, app: Flask) -> None:
        """Within a single request, get_client should return the same instance."""
        OJS(app)
        with app.test_request_context("/"):
            c1 = get_client()
            c2 = get_client()
            assert c1 is c2

    def test_extension_enqueue_in_request(self, app: Flask) -> None:
        with patch("ojs_flask.extension.ojs.SyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            ext = OJS(app)
            with app.test_request_context("/"):
                ext.enqueue("report.generate", [42], queue="reports")
                mock_client.enqueue.assert_called_once_with(
                    "report.generate", [42], queue="reports"
                )

    def test_enqueue_with_none_args(self, app: Flask) -> None:
        with patch("ojs_flask.extension.ojs.SyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            ext = OJS(app)
            with app.test_request_context("/"):
                ext.enqueue("cleanup.run")
                mock_client.enqueue.assert_called_once_with("cleanup.run", None)

    def test_enqueue_with_kwargs(self, app: Flask) -> None:
        with patch("ojs_flask.extension.ojs.SyncClient") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client

            ext = OJS(app)
            with app.test_request_context("/"):
                ext.enqueue(
                    "email.send",
                    ["user@example.com"],
                    queue="email",
                    meta={"tenant": "acme"},
                    priority=5,
                )
                mock_client.enqueue.assert_called_once_with(
                    "email.send",
                    ["user@example.com"],
                    queue="email",
                    meta={"tenant": "acme"},
                    priority=5,
                )
