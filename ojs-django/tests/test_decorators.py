"""Tests for the @ojs_job decorator."""

from __future__ import annotations

import pytest

import ojs

from ojs_django.decorators import _registry, ojs_job


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


def test_ojs_job_duplicate_raises() -> None:
    @ojs_job("test.dup")
    async def handler_one(ctx: ojs.JobContext) -> None:
        pass

    with pytest.raises(ValueError, match="Duplicate handler"):

        @ojs_job("test.dup")
        async def handler_two(ctx: ojs.JobContext) -> None:
            pass
