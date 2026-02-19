"""Tests for OJS FastAPI handler registry and async handlers."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from ojs_fastapi.handlers import OJSHandlerRegistry, JobHandler, ojs_handler  # noqa: E402
from ojs_fastapi.depends import OJSPlugin  # noqa: E402


class TestOJSHandlerRegistry:
    """Tests for the handler registry."""

    def test_register_handler(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        assert "email.send" in registry.registered_types

    def test_register_multiple_handlers(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        @registry.handler("report.generate")
        async def gen_report(ctx: object) -> None:
            pass

        assert registry.registered_types == ["email.send", "report.generate"]

    def test_get_handler_returns_metadata(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send", queue="email", concurrency=5)
        async def send_email(ctx: object) -> None:
            pass

        handler = registry.get_handler("email.send")
        assert handler is not None
        assert isinstance(handler, JobHandler)
        assert handler.type == "email.send"
        assert handler.queue == "email"
        assert handler.concurrency == 5

    def test_get_handler_returns_none_for_unknown(self) -> None:
        registry = OJSHandlerRegistry()
        assert registry.get_handler("unknown.type") is None

    def test_handler_decorator_preserves_function(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        # The function should still be callable
        assert callable(send_email)

    def test_attach_creates_worker(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        plugin = OJSPlugin(url="http://localhost:8080")

        mock_worker = MagicMock()
        _ojs_mock.Worker = MagicMock(return_value=mock_worker)

        registry.attach(plugin)

        _ojs_mock.Worker.assert_called_once_with(
            url="http://localhost:8080",
            queues=["default"],
            concurrency=10,
            poll_interval=2.0,
        )
        mock_worker.register.assert_called_once_with("email.send", send_email)
        assert plugin._worker is mock_worker

    def test_attach_registers_all_handlers(self) -> None:
        registry = OJSHandlerRegistry()

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        @registry.handler("report.generate")
        async def gen_report(ctx: object) -> None:
            pass

        plugin = OJSPlugin(url="http://localhost:8080")
        mock_worker = MagicMock()
        _ojs_mock.Worker = MagicMock(return_value=mock_worker)

        registry.attach(plugin)

        assert mock_worker.register.call_count == 2


class TestOJSHandlerDecorator:
    """Tests for the standalone ojs_handler decorator."""

    def test_ojs_handler_adds_metadata(self) -> None:
        @ojs_handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        assert hasattr(send_email, "_ojs_handler")
        assert send_email._ojs_handler.type == "email.send"

    def test_ojs_handler_with_queue(self) -> None:
        @ojs_handler("email.send", queue="email")
        async def send_email(ctx: object) -> None:
            pass

        assert send_email._ojs_handler.queue == "email"

    def test_ojs_handler_preserves_callable(self) -> None:
        @ojs_handler("email.send")
        async def send_email(ctx: object) -> None:
            pass

        assert callable(send_email)


class TestAsyncHandlerExecution:
    """Tests for async handler execution."""

    @pytest.mark.asyncio
    async def test_handler_can_be_awaited(self) -> None:
        registry = OJSHandlerRegistry()
        results: list[str] = []

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            results.append("sent")

        handler = registry.get_handler("email.send")
        assert handler is not None
        await handler.handler(MagicMock())
        assert results == ["sent"]

    @pytest.mark.asyncio
    async def test_handler_receives_context(self) -> None:
        registry = OJSHandlerRegistry()
        received_ctx = None

        @registry.handler("email.send")
        async def send_email(ctx: object) -> None:
            nonlocal received_ctx
            received_ctx = ctx

        handler = registry.get_handler("email.send")
        assert handler is not None
        mock_ctx = MagicMock()
        mock_ctx.args = ["user@example.com"]
        await handler.handler(mock_ctx)
        assert received_ctx is mock_ctx
