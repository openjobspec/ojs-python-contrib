"""Tests for the OJS health check blueprint."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from ojs_flask import OJS
from ojs_flask.health import create_health_blueprint


@pytest.fixture()
def app() -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    OJS(app)
    app.register_blueprint(create_health_blueprint())
    return app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


class TestHealthEndpoint:
    """Tests for the /ojs/health endpoint."""

    def test_health_endpoint_returns_healthy(self, client: FlaskClient) -> None:
        """Health endpoint should return 200 when OJS server is reachable."""
        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.list_queues.return_value = ["default", "email"]
            mock_get_client.return_value = mock_client

            response = client.get("/ojs/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["queues"] == 2

    def test_health_endpoint_returns_unhealthy_on_error(
        self, client: FlaskClient
    ) -> None:
        """Health endpoint should return 503 when OJS server is unreachable."""
        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_get_client.side_effect = ConnectionError("Connection refused")

            response = client.get("/ojs/health")

        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["status"] == "unhealthy"
        assert "Connection refused" in data["error"]

    def test_health_endpoint_unhealthy_on_list_queues_error(
        self, client: FlaskClient
    ) -> None:
        """Health endpoint should return 503 when list_queues fails."""
        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.list_queues.side_effect = RuntimeError("Server error")
            mock_get_client.return_value = mock_client

            response = client.get("/ojs/health")

        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["status"] == "unhealthy"


class TestStatusEndpoint:
    """Tests for the /ojs/status endpoint."""

    def test_status_endpoint_returns_queue_info(self, client: FlaskClient) -> None:
        """Status endpoint should return detailed queue information."""
        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.list_queues.return_value = ["default", "email"]
            mock_client.queue_stats.side_effect = [
                {"pending": 5, "active": 2},
                {"pending": 0, "active": 1},
            ]
            mock_get_client.return_value = mock_client

            response = client.get("/ojs/status")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert len(data["queues"]) == 2
        assert data["queues"][0]["name"] == "default"
        assert data["queues"][0]["stats"] == {"pending": 5, "active": 2}
        assert data["queues"][1]["name"] == "email"

    def test_status_endpoint_unhealthy_on_error(self, client: FlaskClient) -> None:
        """Status endpoint should return 503 when OJS server is unreachable."""
        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_get_client.side_effect = ConnectionError("Connection refused")

            response = client.get("/ojs/status")

        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["status"] == "unhealthy"


class TestCustomURLPrefix:
    """Tests for custom URL prefix on the health blueprint."""

    def test_custom_url_prefix(self) -> None:
        """Blueprint should use the custom URL prefix."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        OJS(app)
        app.register_blueprint(create_health_blueprint(url_prefix="/jobs"))

        test_client = app.test_client()

        with patch("ojs_flask.helpers.get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.list_queues.return_value = []
            mock_get_client.return_value = mock_client

            response = test_client.get("/jobs/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"


class TestHealthWithoutExtension:
    """Tests for health endpoints when OJS extension is not initialized."""

    def test_health_without_extension_raises(self) -> None:
        """Health endpoint should return 503 when extension is not initialized."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(create_health_blueprint())

        test_client = app.test_client()
        response = test_client.get("/ojs/health")

        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["status"] == "unhealthy"
