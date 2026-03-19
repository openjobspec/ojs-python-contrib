"""Tests for the AgentCore exporter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from ojs_agentcore import AgentCoreExporter, AgentCoreSession


@pytest.fixture
def exporter() -> AgentCoreExporter:
    return AgentCoreExporter("http://localhost:8080")


def test_exporter_init():
    e = AgentCoreExporter()
    assert e._ojs_url == "http://localhost:8080"


def test_exporter_custom_url():
    e = AgentCoreExporter("https://ojs.example.com/")
    assert e._ojs_url == "https://ojs.example.com"


def test_to_ojs_envelope(exporter: AgentCoreExporter):
    session = AgentCoreSession(
        session_id="sess-001",
        agent_id="agent-abc",
        created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        turns=[{"role": "user", "content": "hello"}],
        status="completed",
    )
    envelope = exporter._to_ojs_envelope(session)

    assert envelope["type"] == "agentcore.session"
    assert envelope["args"] == ["sess-001"]
    assert envelope["ext_agent_v2"]["source"] == "aws-bedrock-agentcore"
    assert envelope["ext_agent_v2"]["agent_id"] == "agent-abc"
    assert envelope["ext_agent_v2"]["session_id"] == "sess-001"
    assert envelope["ext_agent_v2"]["turn_count"] == 1
    assert envelope["ext_agent_v2"]["state"] == "completed"


def test_status_mapping(exporter: AgentCoreExporter):
    for status, expected in [
        ("completed", "completed"),
        ("in_progress", "running"),
        ("failed", "failed"),
        ("cancelled", "cancelled"),
        ("unknown", "pending"),
        ("something_else", "pending"),
    ]:
        session = AgentCoreSession(
            session_id="s1",
            agent_id="a1",
            created_at=datetime.now(timezone.utc),
            status=status,
        )
        envelope = exporter._to_ojs_envelope(session)
        assert envelope["ext_agent_v2"]["state"] == expected


@pytest.mark.asyncio
async def test_export_session(exporter: AgentCoreExporter):
    envelope = await exporter.export_session("test-session")
    assert envelope["type"] == "agentcore.session"
    assert envelope["args"] == ["test-session"]


@pytest.mark.asyncio
async def test_export_all(exporter: AgentCoreExporter):
    envelopes = await exporter.export_all("agent-1", limit=10)
    assert len(envelopes) >= 1
    assert envelopes[0]["type"] == "agentcore.session"
