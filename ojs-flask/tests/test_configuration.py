"""Tests for Flask extension configuration handling."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from flask import Flask

from ojs_flask import OJS


@pytest.fixture
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


class TestConfigurationDefaults:
    """Tests for default configuration values."""

    def test_ojs_url_default(self, app: Flask) -> None:
        OJS(app)
        assert app.config["OJS_URL"] == "http://localhost:8080"

    def test_ojs_queues_default(self, app: Flask) -> None:
        OJS(app)
        assert app.config["OJS_QUEUES"] == ["default"]

    def test_defaults_not_overwritten(self, app: Flask) -> None:
        """Pre-set config values should not be overwritten by defaults."""
        app.config["OJS_URL"] = "http://custom:9090"
        app.config["OJS_QUEUES"] = ["high", "low"]
        OJS(app)
        assert app.config["OJS_URL"] == "http://custom:9090"
        assert app.config["OJS_QUEUES"] == ["high", "low"]


class TestConfigurationCustom:
    """Tests for custom configuration values."""

    def test_custom_url_passed_to_client(self, app: Flask) -> None:
        app.config["OJS_URL"] = "http://ojs-server:3000"
        with patch("ojs_flask.extension.ojs.SyncClient") as mock_cls:
            OJS(app)
            mock_cls.assert_called_once_with("http://ojs-server:3000")

    def test_empty_queues_list(self, app: Flask) -> None:
        app.config["OJS_QUEUES"] = []
        OJS(app)
        assert app.config["OJS_QUEUES"] == []

    def test_multiple_queues(self, app: Flask) -> None:
        app.config["OJS_QUEUES"] = ["email", "reports", "notifications"]
        OJS(app)
        assert len(app.config["OJS_QUEUES"]) == 3
