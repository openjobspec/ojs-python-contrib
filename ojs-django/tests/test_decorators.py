"""Tests for the @ojs_job decorator."""

from __future__ import annotations

import pytest

import ojs

from ojs_django.decorators import OJSJobWrapper, _registry, ojs_job


@pytest.fixture(autouse=True)
def _clear_registry() -> None:  # type: ignore[misc]
    """Clear the handler registry between tests."""
    _registry.clear()


def test_ojs_job_registers_handler() -> None:
    @ojs_job("test.ping")
    async def handle_ping(ctx: ojs.JobContext) -> None:
        pass

    assert "test.ping" in _registry
    assert _registry["test.ping"] is handle_ping
    assert _registry["test.ping"].fn.__name__ == "handle_ping"


def test_ojs_job_duplicate_raises() -> None:
    @ojs_job("test.dup")
    async def handler_one(ctx: ojs.JobContext) -> None:
        pass

    with pytest.raises(ValueError, match="Duplicate handler"):

        @ojs_job("test.dup")
        async def handler_two(ctx: ojs.JobContext) -> None:
            pass


def test_ojs_job_returns_wrapper() -> None:
    @ojs_job("test.wrapper")
    async def handler(ctx: ojs.JobContext) -> None:
        pass

    assert isinstance(handler, OJSJobWrapper)
    assert handler.job_type == "test.wrapper"


def test_ojs_job_with_options() -> None:
    retry = ojs.RetryPolicy(max_attempts=5)

    @ojs_job("test.options", queue="high", retry=retry, priority=10, tags=["critical"])
    async def handler(ctx: ojs.JobContext) -> None:
        pass

    assert handler.queue == "high"
    assert handler.retry == retry
    assert handler.priority == 10
    assert handler.tags == ["critical"]


@pytest.mark.asyncio
async def test_ojs_job_wrapper_callable() -> None:
    """Wrapper can be called directly as a handler."""

    @ojs_job("test.callable")
    async def handler(ctx: ojs.JobContext) -> str:
        return "done"

    job = ojs.Job(id="test-id", type="test.callable", state=ojs.JobState.ACTIVE)
    ctx = ojs.JobContext(job=job)
    result = await handler(ctx)
    assert result == "done"


def test_ojs_job_enqueue_method_exists() -> None:
    @ojs_job("test.enqueue")
    async def handler(ctx: ojs.JobContext) -> None:
        pass

    assert hasattr(handler, "enqueue")
    assert hasattr(handler, "enqueue_after_commit")
