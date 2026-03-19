"""Tests for the OJS LangGraph adapter."""

from __future__ import annotations

import asyncio
from typing import Any


class FakeGraph:
    """Fake LangGraph compiled graph for testing."""

    def __init__(self, output: Any = None) -> None:
        self._output = output or {"result": "ok"}
        self.invoke_count = 0

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None) -> Any:
        self.invoke_count += 1
        return self._output


class ErrorGraph:
    """Fake graph that raises on invoke."""

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None) -> Any:
        raise ValueError("graph exploded")


def test_durable_passthrough() -> None:
    """Durable wrapper should pass through to the underlying graph."""
    from ojs_langgraph import durable

    fake = FakeGraph(output={"answer": "42"})
    wrapped = durable(fake, ojs_url="http://test:8080")

    result = asyncio.get_event_loop().run_until_complete(
        wrapped.ainvoke({"query": "meaning of life"})
    )
    assert result == {"answer": "42"}
    assert fake.invoke_count == 1
    assert wrapped.step_count == 1


def test_durable_step_counting() -> None:
    """Step counter should increment on each invocation."""
    from ojs_langgraph import durable

    fake = FakeGraph()
    wrapped = durable(fake)

    loop = asyncio.get_event_loop()
    for _ in range(5):
        loop.run_until_complete(wrapped.ainvoke({"x": 1}))

    assert wrapped.step_count == 5
    assert fake.invoke_count == 5


def test_durable_config_passthrough() -> None:
    """Config should be passed through to the graph."""
    from ojs_langgraph import DurableGraph

    class ConfigCapture:
        captured_config = None

        async def ainvoke(self, input: Any, config: dict[str, Any] | None = None) -> Any:
            self.captured_config = config
            return {}

    graph = ConfigCapture()
    dg = DurableGraph(graph, ojs_url="http://test:8080")

    cfg = {"thread_id": "abc"}
    asyncio.get_event_loop().run_until_complete(dg.ainvoke({}, config=cfg))
    assert graph.captured_config == cfg


def test_durable_policy() -> None:
    """Policy should be stored on the wrapper."""
    from ojs_langgraph import durable

    fake = FakeGraph()
    wrapped = durable(fake, policy={"retry": 3, "timeout": 60})
    assert wrapped._policy == {"retry": 3, "timeout": 60}


def test_step_recording() -> None:
    """Steps should be recorded with timestamps and snapshots."""
    from ojs_langgraph import durable

    fake = FakeGraph(output={"answer": "42"})
    wrapped = durable(fake)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(wrapped.ainvoke({"query": "hello"}))
    loop.run_until_complete(wrapped.ainvoke({"query": "world"}))

    steps = wrapped.steps
    assert len(steps) == 2

    assert steps[0].index == 1
    assert steps[0].input_snapshot == {"query": "hello"}
    assert steps[0].output_snapshot == {"answer": "42"}
    assert steps[0].started_at is not None
    assert steps[0].finished_at is not None
    assert steps[0].error is None

    assert steps[1].index == 2
    assert steps[1].input_snapshot == {"query": "world"}


def test_step_recording_on_error() -> None:
    """Steps should record errors when the graph raises."""
    from ojs_langgraph import durable

    wrapped = durable(ErrorGraph())
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(wrapped.ainvoke({"x": 1}))
        assert False, "Expected ValueError"
    except ValueError:
        pass

    steps = wrapped.steps
    assert len(steps) == 1
    assert steps[0].error == "graph exploded"
    assert steps[0].output_snapshot is None


def test_to_ojs_envelope() -> None:
    """to_ojs_envelope should produce an OJS envelope with ext_agent_v2."""
    from ojs_langgraph import durable

    fake = FakeGraph(output={"result": "done"})
    wrapped = durable(fake, job_type="agent.custom", policy={"retry": 2})

    loop = asyncio.get_event_loop()
    loop.run_until_complete(wrapped.ainvoke({"input": "test"}))

    envelope = wrapped.to_ojs_envelope()

    assert envelope["type"] == "agent.custom"
    assert "id" in envelope
    assert envelope["meta"]["agent_provider"] == "langgraph"
    assert envelope["meta"]["step_count"] == 1

    ext = envelope["ext_agent_v2"]
    assert ext["provider"] == "langgraph"
    assert ext["job_type"] == "agent.custom"
    assert len(ext["steps"]) == 1
    assert ext["steps"][0]["input_snapshot"] == {"input": "test"}
    assert ext["steps"][0]["output_snapshot"] == {"result": "done"}
    assert ext["policy"] == {"retry": 2}


def test_steps_property_returns_copy() -> None:
    """steps property should return a copy, not the internal list."""
    from ojs_langgraph import durable

    fake = FakeGraph()
    wrapped = durable(fake)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(wrapped.ainvoke({"x": 1}))

    steps1 = wrapped.steps
    steps2 = wrapped.steps
    assert steps1 is not steps2
    assert len(steps1) == len(steps2)
