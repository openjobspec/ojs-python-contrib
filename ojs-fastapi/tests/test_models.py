"""Tests for OJS FastAPI Pydantic models and error responses."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

_ojs_mock = sys.modules.get("ojs") or MagicMock()
sys.modules.setdefault("ojs", _ojs_mock)

from fastapi import Depends, FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from ojs_fastapi import OJSPlugin, get_ojs_client  # noqa: E402
from ojs_fastapi.models import EnqueueRequest, EnqueueResponse, JobResponse  # noqa: E402


class TestEnqueueRequest:
    """Tests for EnqueueRequest Pydantic model."""

    def test_minimal_request(self) -> None:
        req = EnqueueRequest(type="email.send")
        assert req.type == "email.send"
        assert req.args == []
        assert req.queue == "default"
        assert req.meta == {}
        assert req.priority == 0

    def test_full_request(self) -> None:
        req = EnqueueRequest(
            type="email.send",
            args=["user@example.com", "Hello"],
            queue="email",
            meta={"tenant": "acme"},
            priority=10,
        )
        assert req.type == "email.send"
        assert req.args == ["user@example.com", "Hello"]
        assert req.queue == "email"
        assert req.meta == {"tenant": "acme"}
        assert req.priority == 10

    def test_request_serialization(self) -> None:
        req = EnqueueRequest(type="report.generate", args=[42])
        data = req.model_dump()
        assert data["type"] == "report.generate"
        assert data["args"] == [42]


class TestEnqueueResponse:
    """Tests for EnqueueResponse Pydantic model."""

    def test_response_fields(self) -> None:
        resp = EnqueueResponse(
            job_id="01912345-6789-7abc-def0-123456789abc",
            type="email.send",
            state="available",
            queue="default",
        )
        assert resp.job_id == "01912345-6789-7abc-def0-123456789abc"
        assert resp.type == "email.send"
        assert resp.state == "available"
        assert resp.queue == "default"


class TestJobResponse:
    """Tests for JobResponse Pydantic model."""

    def test_minimal_response(self) -> None:
        resp = JobResponse(
            job_id="test-id",
            type="email.send",
            state="active",
        )
        assert resp.job_id == "test-id"
        assert resp.queue == "default"
        assert resp.args == []
        assert resp.meta == {}
        assert resp.priority == 0
        assert resp.attempt == 0
        assert resp.created_at is None
        assert resp.result is None

    def test_full_response(self) -> None:
        resp = JobResponse(
            job_id="test-id",
            type="email.send",
            state="completed",
            queue="email",
            args=["user@example.com"],
            meta={"tenant": "acme"},
            priority=5,
            attempt=2,
            created_at="2025-01-01T00:00:00Z",
            enqueued_at="2025-01-01T00:00:01Z",
            started_at="2025-01-01T00:00:02Z",
            completed_at="2025-01-01T00:00:03Z",
            result={"sent": True},
        )
        assert resp.attempt == 2
        assert resp.result == {"sent": True}
        assert resp.completed_at == "2025-01-01T00:00:03Z"


class TestErrorResponses:
    """Tests for error responses from FastAPI endpoints."""

    @pytest.mark.asyncio
    async def test_missing_type_field_returns_422(self) -> None:
        plugin = OJSPlugin(url="http://localhost:8080")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        plugin._client = mock_client

        app = FastAPI()
        app.state.ojs_plugin = plugin

        @app.post("/jobs", response_model=EnqueueResponse)
        async def enqueue_job(
            body: EnqueueRequest,
            client: Any = Depends(get_ojs_client),
        ) -> EnqueueResponse:
            job = await client.enqueue(body.type, body.args)
            return EnqueueResponse(
                job_id=job.id, type=job.type, state=str(job.state), queue=job.queue
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/jobs", json={})
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_json_returns_422(self) -> None:
        plugin = OJSPlugin(url="http://localhost:8080")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        plugin._client = mock_client

        app = FastAPI()
        app.state.ojs_plugin = plugin

        @app.post("/jobs", response_model=EnqueueResponse)
        async def enqueue_job(
            body: EnqueueRequest,
            client: Any = Depends(get_ojs_client),
        ) -> EnqueueResponse:
            job = await client.enqueue(body.type, body.args)
            return EnqueueResponse(
                job_id=job.id, type=job.type, state=str(job.state), queue=job.queue
            )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/jobs",
                content="not valid json",
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 422


class TestPluginErrors:
    """Tests for OJSPlugin error handling."""

    def test_client_not_started_raises(self) -> None:
        plugin = OJSPlugin(url="http://localhost:8080")
        with pytest.raises(RuntimeError, match="OJS client has not been started"):
            _ = plugin.client

    def test_worker_defaults_to_none(self) -> None:
        plugin = OJSPlugin(url="http://localhost:8080")
        assert plugin.worker is None
