"""Tests for the ojs-flask extension."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from ojs_flask import OJS, enqueue, get_client


@pytest.fixture()
def app() -> Flask:
    """Create a minimal Flask application for testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestOJSExtension:
    """Tests for the OJS Flask extension lifecycle."""

    def test_init_app_registers_extension(self, app: Flask) -> None:
        ext = OJS()
        ext.init_app(app)
        assert "ojs" in app.extensions

    def test_direct_init(self, app: Flask) -> None:
        OJS(app)
        assert "ojs" in app.extensions

    def test_default_config(self, app: Flask) -> None:
        OJS(app)
        assert app.config["OJS_URL"] == "http://localhost:8080"
        assert app.config["OJS_QUEUES"] == ["default"]

    def test_custom_config(self, app: Flask) -> None:
        app.config["OJS_URL"] = "http://ojs:9090"
        app.config["OJS_QUEUES"] = ["email", "reports"]
        OJS(app)
        assert app.config["OJS_URL"] == "http://ojs:9090"
        assert app.config["OJS_QUEUES"] == ["email", "reports"]

    def test_client_property_within_app_context(self, app: Flask) -> None:
        ext = OJS(app)
        with app.app_context():
            client = ext.client
            assert client is app.extensions["ojs"]

    def test_client_property_without_init_raises(self, app: Flask) -> None:
        ext = OJS()
        with app.app_context(), pytest.raises(RuntimeError, match="OJS extension not initialized"):
            _ = ext.client


class TestHelpers:
    """Tests for module-level helper functions."""

    def test_get_client_returns_extension_client(self, app: Flask) -> None:
        OJS(app)
        with app.app_context():
            client = get_client()
            assert client is app.extensions["ojs"]

    def test_get_client_without_extension_raises(self, app: Flask) -> None:
        with app.app_context(), pytest.raises(RuntimeError, match="OJS extension not initialized"):
            get_client()

    @patch("ojs_flask.helpers.get_client")
    def test_enqueue_delegates_to_client(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        enqueue("email.send", ["user@example.com"], queue="email", meta={"urgent": True})

        mock_client.enqueue.assert_called_once_with(
            "email.send",
            ["user@example.com"],
            queue="email",
            meta={"urgent": True},
        )

    @patch("ojs_flask.helpers.get_client")
    def test_enqueue_returns_job(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        sentinel: Any = object()
        mock_client.enqueue.return_value = sentinel
        mock_get_client.return_value = mock_client

        result = enqueue("report.generate", [42])

        assert result is sentinel


class TestExtensionEnqueue:
    """Tests for the OJS.enqueue convenience method."""

    @patch("ojs_flask.extension.ojs.SyncClient")
    def test_enqueue_via_extension(self, mock_sync_client_cls: MagicMock, app: Flask) -> None:
        mock_client = MagicMock()
        mock_sync_client_cls.return_value = mock_client

        ext = OJS(app)
        with app.app_context():
            ext.enqueue("data.import", ["/tmp/file.csv"], queue="imports")

        mock_client.enqueue.assert_called_once_with(
            "data.import",
            ["/tmp/file.csv"],
            queue="imports",
        )
