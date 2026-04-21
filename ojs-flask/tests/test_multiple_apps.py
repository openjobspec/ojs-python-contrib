"""Tests for Flask extension with multiple applications."""

from __future__ import annotations

import pytest
from flask import Flask

from ojs_flask import OJS, get_client


@pytest.fixture
def app1() -> Flask:
    app = Flask("app1")
    app.config["TESTING"] = True
    app.config["OJS_URL"] = "http://ojs-1:8080"
    return app


@pytest.fixture
def app2() -> Flask:
    app = Flask("app2")
    app.config["TESTING"] = True
    app.config["OJS_URL"] = "http://ojs-2:9090"
    return app


class TestMultipleApps:
    """Tests for using OJS with multiple Flask applications."""

    def test_init_app_on_multiple_apps(self, app1: Flask, app2: Flask) -> None:
        ext = OJS()
        ext.init_app(app1)
        ext.init_app(app2)
        assert "ojs" in app1.extensions
        assert "ojs" in app2.extensions

    def test_each_app_has_own_client(self, app1: Flask, app2: Flask) -> None:
        ext = OJS()
        ext.init_app(app1)
        ext.init_app(app2)

        with app1.app_context():
            client1 = ext.client
        with app2.app_context():
            client2 = ext.client

        assert client1 is not client2

    def test_each_app_has_own_config(self, app1: Flask, app2: Flask) -> None:
        ext = OJS()
        ext.init_app(app1)
        ext.init_app(app2)
        assert app1.config["OJS_URL"] == "http://ojs-1:8080"
        assert app2.config["OJS_URL"] == "http://ojs-2:9090"

    def test_get_client_returns_correct_app_client(self, app1: Flask, app2: Flask) -> None:
        ext = OJS()
        ext.init_app(app1)
        ext.init_app(app2)

        with app1.app_context():
            c1 = get_client()
            assert c1 is app1.extensions["ojs"]

        with app2.app_context():
            c2 = get_client()
            assert c2 is app2.extensions["ojs"]

    def test_separate_extensions_per_app(self) -> None:
        app_a = Flask("a")
        app_b = Flask("b")
        app_a.config["OJS_URL"] = "http://a:8080"
        app_b.config["OJS_URL"] = "http://b:8080"

        ext_a = OJS(app_a)
        ext_b = OJS(app_b)

        with app_a.app_context():
            assert ext_a.client is app_a.extensions["ojs"]

        with app_b.app_context():
            assert ext_b.client is app_b.extensions["ojs"]


class TestFactoryPattern:
    """Tests for the application factory pattern."""

    def test_factory_pattern_deferred_init(self) -> None:
        ext = OJS()

        def create_app(url: str) -> Flask:
            app = Flask(__name__)
            app.config["OJS_URL"] = url
            ext.init_app(app)
            return app

        app1 = create_app("http://app1:8080")
        app2 = create_app("http://app2:8080")

        assert "ojs" in app1.extensions
        assert "ojs" in app2.extensions
        assert app1.config["OJS_URL"] == "http://app1:8080"
        assert app2.config["OJS_URL"] == "http://app2:8080"
