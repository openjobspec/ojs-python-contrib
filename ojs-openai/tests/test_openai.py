"""Tests for the OJS OpenAI adapter."""

from __future__ import annotations

import asyncio
from typing import Any


class FakeAgent:
    """Mock OpenAI agent for testing."""

    def __init__(self, name: str = "test-agent", output: Any = None) -> None:
        self.name = name
        self._output = output or {"response": "Hello!"}
        self.run_count = 0

    async def arun(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        self.run_count += 1
        return self._output


class ToolCallingAgent:
    """Mock agent that returns tool calls in its result."""

    def __init__(self, name: str = "tool-agent") -> None:
        self.name = name

    async def arun(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        return {
            "response": "I used tools",
            "tool_calls": [
                {"name": "search", "args": {"q": "hello"}, "result": "found it", "duration_ms": 42},
                {"name": "calculate", "args": {"expr": "1+1"}, "result": "2", "duration_ms": 5},
            ],
        }


class SyncAgent:
    """Mock agent with only a synchronous run method."""

    def __init__(self, name: str = "sync-agent", output: Any = None) -> None:
        self.name = name
        self._output = output or {"response": "sync"}

    def run(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        return self._output


class NoRunAgent:
    """Mock agent with no run method."""

    name = "broken"


def test_wrap_run_async() -> None:
    """wrap_run should call arun and record the result."""
    from ojs_openai import OpenAIAdapter, AdapterConfig

    config = AdapterConfig(ojs_url="http://test:8080")
    adapter = OpenAIAdapter(config)
    agent = FakeAgent(output={"answer": "42"})
    messages = [{"role": "user", "content": "hello"}]

    record = asyncio.get_event_loop().run_until_complete(
        adapter.wrap_run(agent, messages)
    )

    assert record.run_id == "run-1"
    assert record.agent_name == "test-agent"
    assert record.result == {"answer": "42"}
    assert agent.run_count == 1


def test_wrap_run_sync_fallback() -> None:
    """wrap_run should fall back to sync run method."""
    from ojs_openai import OpenAIAdapter

    adapter = OpenAIAdapter()
    agent = SyncAgent()
    messages = [{"role": "user", "content": "hi"}]

    record = asyncio.get_event_loop().run_until_complete(
        adapter.wrap_run(agent, messages)
    )

    assert record.result == {"response": "sync"}


def test_wrap_run_no_method() -> None:
    """wrap_run should raise TypeError for agents without run."""
    from ojs_openai import OpenAIAdapter

    adapter = OpenAIAdapter()
    agent = NoRunAgent()

    try:
        asyncio.get_event_loop().run_until_complete(
            adapter.wrap_run(agent, [])
        )
        assert False, "Expected TypeError"
    except TypeError as e:
        assert "no 'run' or 'arun' method" in str(e)


def test_export_session() -> None:
    """export_session should return an OJS envelope with ext_agent_v2."""
    from ojs_openai import OpenAIAdapter, AdapterConfig

    config = AdapterConfig(job_type="agent.custom")
    adapter = OpenAIAdapter(config)
    agent = FakeAgent(name="my-agent")

    record = asyncio.get_event_loop().run_until_complete(
        adapter.wrap_run(agent, [{"role": "user", "content": "test"}])
    )

    envelope = asyncio.get_event_loop().run_until_complete(
        adapter.export_session(record.run_id)
    )

    assert envelope["type"] == "agent.custom"
    assert "id" in envelope
    assert envelope["meta"]["agent_provider"] == "openai"
    assert envelope["meta"]["agent_name"] == "my-agent"
    assert envelope["meta"]["tool_call_count"] == 0

    ext = envelope["ext_agent_v2"]
    assert ext["provider"] == "openai"
    assert ext["agent_name"] == "my-agent"
    assert ext["tool_calls"] == []


def test_export_session_not_found() -> None:
    """export_session should raise KeyError for unknown run_id."""
    from ojs_openai import OpenAIAdapter

    adapter = OpenAIAdapter()

    try:
        asyncio.get_event_loop().run_until_complete(
            adapter.export_session("nonexistent")
        )
        assert False, "Expected KeyError"
    except KeyError:
        pass


def test_tool_call_recording() -> None:
    """wrap_run should record tool calls from the agent result."""
    from ojs_openai import OpenAIAdapter, AdapterConfig

    config = AdapterConfig(ojs_url="http://test:8080")
    adapter = OpenAIAdapter(config)
    agent = ToolCallingAgent()
    messages = [{"role": "user", "content": "use tools"}]

    record = asyncio.get_event_loop().run_until_complete(
        adapter.wrap_run(agent, messages)
    )

    assert len(record.tool_calls) == 2
    assert record.tool_calls[0]["name"] == "search"
    assert record.tool_calls[0]["args"] == {"q": "hello"}
    assert record.tool_calls[0]["result"] == "found it"
    assert record.tool_calls[0]["duration_ms"] == 42
    assert record.tool_calls[1]["name"] == "calculate"


def test_tool_calls_in_envelope() -> None:
    """Tool calls should appear in the exported envelope's ext_agent_v2."""
    from ojs_openai import OpenAIAdapter

    adapter = OpenAIAdapter()
    agent = ToolCallingAgent()

    record = asyncio.get_event_loop().run_until_complete(
        adapter.wrap_run(agent, [{"role": "user", "content": "hi"}])
    )
    envelope = asyncio.get_event_loop().run_until_complete(
        adapter.export_session(record.run_id)
    )

    assert envelope["meta"]["tool_call_count"] == 2
    ext = envelope["ext_agent_v2"]
    assert len(ext["tool_calls"]) == 2
    assert ext["tool_calls"][0]["name"] == "search"
