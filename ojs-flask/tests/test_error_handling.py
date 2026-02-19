"""Tests for Flask extension error handling."""

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


class TestClientAccessErrors:
    """Tests for error handling when accessing the OJS client."""

    def test_client_outside_app_context_raises(self) -> None:
        ext = OJS()
        with pytest.raises(RuntimeError):
            _ = ext.client

    def test_get_client_outside_app_context_raises(self) -> None:
        with pytest.raises(RuntimeError):
            get_client()

    def test_client_without_init_raises_with_message(self, app: Flask) -> None:
        ext = OJS()
        with app.app_context():
            with pytest.raises(RuntimeError, match="OJS extension not initialized"):
                _ = ext.client

    def test_get_client_without_init_raises_with_message(self, app: Flask) -> None:
        with app.app_context():
            with pytest.raises(RuntimeError, match="OJS extension not initialized"):
                get_client()


class TestEnqueueErrors:
    """Tests for error handling during job enqueueing."""

    def test_enqueue_without_app_context_raises(self) -> None:
        with pytest.raises(RuntimeError):
            enqueue("email.send", ["user@example.com"])

    def test_enqueue_without_extension_raises(self, app: Flask) -> None:
        with app.app_context():
            with pytest.raises(RuntimeError, match="OJS extension not initialized"):
                enqueue("email.send", ["user@example.com"])

    @patch("ojs_flask.helpers.get_client")
    def test_enqueue_propagates_client_error(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.enqueue.side_effect = ConnectionError("Connection refused")
        mock_get_client.return_value = mock_client

        with pytest.raises(ConnectionError, match="Connection refused"):
            enqueue("email.send", ["user@example.com"])


class TestTeardown:
    """Tests for the extension teardown callback."""

    def test_teardown_registered(self, app: Flask) -> None:
        OJS(app)
        assert len(app.teardown_appcontext_funcs) > 0

    def test_teardown_callback_is_registered(self, app: Flask) -> None:
        """Teardown is registered as an appcontext teardown function."""
        OJS(app)
        # The static method _teardown should be in the teardown funcs
        assert OJS._teardown in app.teardown_appcontext_funcs

    def test_teardown_handles_exception(self, app: Flask) -> None:
        """Teardown should not raise even when called with an exception."""
        OJS(app)
        # _teardown accepts an exc parameter and should be a no-op
        OJS._teardown(ValueError("test error"))
