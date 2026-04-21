"""Tests for OJS FastAPI cron bridge."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from ojs_fastapi.cron import CronRegistration, OJSCronBridge  # noqa: E402

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_register_cron_job() -> None:
    """register should add a CronRegistration entry."""
    cron = OJSCronBridge()
    reg = cron.register("reports.daily", "0 6 * * *", queue="reports")

    assert isinstance(reg, CronRegistration)
    assert reg.job_type == "reports.daily"
    assert reg.schedule == "0 6 * * *"
    assert reg.queue == "reports"
    assert reg.args == []
    assert reg.meta == {}


def test_register_multiple_crons() -> None:
    """Multiple cron jobs can be registered."""
    cron = OJSCronBridge()
    cron.register("reports.daily", "0 6 * * *")
    cron.register("cleanup.stale", "0 */4 * * *", args=["30d"])

    assert len(cron.registrations) == 2
    assert cron.registrations[0].job_type == "reports.daily"
    assert cron.registrations[1].job_type == "cleanup.stale"
    assert cron.registrations[1].args == ["30d"]


def test_registrations_property() -> None:
    """registrations should return a copy of the internal list."""
    cron = OJSCronBridge()
    cron.register("job.a", "* * * * *")
    regs = cron.registrations

    # Mutating the returned list should not affect the bridge
    regs.clear()
    assert len(cron.registrations) == 1


@pytest.mark.asyncio
async def test_sync_calls_register_cron_job() -> None:
    """sync should call client.register_cron_job for each registration."""
    cron = OJSCronBridge()
    metadata = {"tenant": "acme", "trace_context": None}
    cron.register(
        "reports.daily",
        "0 6 * * *",
        queue="reports",
        meta=metadata,
    )
    default_registration = cron.register("cleanup.stale", "0 */4 * * *", meta=None)

    mock_client = AsyncMock()
    mock_result_a = MagicMock(id="cron-1")
    mock_result_b = MagicMock(id="cron-2")
    mock_client.register_cron_job = AsyncMock(side_effect=[mock_result_a, mock_result_b])

    results = await cron.sync(mock_client)

    assert len(results) == 2
    assert results[0].id == "cron-1"
    assert results[1].id == "cron-2"
    assert mock_client.register_cron_job.await_count == 2
    # Public registration fields must be forwarded unchanged to the SDK.
    first_call = mock_client.register_cron_job.await_args_list[0]
    assert first_call.kwargs["name"] == "reports.daily"
    assert first_call.kwargs["cron"] == "0 6 * * *"
    assert first_call.kwargs["job_type"] == "reports.daily"
    assert first_call.kwargs["queue"] == "reports"
    assert first_call.kwargs["meta"] is metadata

    second_call = mock_client.register_cron_job.await_args_list[1]
    assert default_registration.meta == {}
    assert second_call.kwargs["meta"] is default_registration.meta


@pytest.mark.asyncio
async def test_sync_handles_failure() -> None:
    """sync should log errors and continue when a registration fails."""
    cron = OJSCronBridge()
    cron.register("reports.daily", "0 6 * * *")
    cron.register("cleanup.stale", "0 */4 * * *")

    mock_client = AsyncMock()
    mock_result = MagicMock(id="cron-2")
    mock_client.register_cron_job = AsyncMock(
        side_effect=[RuntimeError("server error"), mock_result]
    )

    results = await cron.sync(mock_client)

    # Only the second registration succeeds
    assert len(results) == 1
    assert results[0].id == "cron-2"
    assert mock_client.register_cron_job.await_count == 2
