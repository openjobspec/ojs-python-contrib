"""OJS adapter for OpenAI Agents SDK.

Maps OpenAI agent sessions to OJS durable envelopes, enabling
persistence, replay, and cross-provider portability.

Usage::

    from ojs_openai import OpenAIAdapter, AdapterConfig

    config = AdapterConfig(ojs_url="http://localhost:8080")
    adapter = OpenAIAdapter(config)

    result = await adapter.wrap_run(agent, messages)
    envelope = await adapter.export_session(result.run_id)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable
import time
import uuid


@runtime_checkable
class OpenAIAgentLike(Protocol):
    """Protocol for objects that behave like an OpenAI agent."""

    name: str

    def run(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any: ...


@dataclass
class AdapterConfig:
    """Configuration for the OpenAI → OJS adapter.

    Attributes:
        ojs_url: Base URL of the OJS server.
        job_type: OJS job type for agent runs.
        record_tools: Whether to record tool calls in the OJS envelope.
    """

    ojs_url: str = "http://localhost:8080"
    job_type: str = "agent.openai"
    record_tools: bool = True


@dataclass
class RunRecord:
    """Internal record of a wrapped agent run.

    Attributes:
        run_id: Unique identifier for this run.
        agent_name: Name of the agent that was executed.
        messages: Input messages provided to the agent.
        result: The agent's output.
        tool_calls: Recorded tool calls, if any.
    """

    run_id: str
    agent_name: str
    messages: list[dict[str, Any]]
    result: Any = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class OpenAIAdapter:
    """Wraps OpenAI agent runs with OJS durability.

    This P1 prototype records agent executions and maps them to OJS
    envelopes. The full P2 implementation will persist state to the
    OJS server and support replay and cross-provider portability.
    """

    def __init__(self, config: AdapterConfig | None = None) -> None:
        self._config = config or AdapterConfig()
        self._runs: dict[str, RunRecord] = {}
        self._run_counter = 0

    async def wrap_run(
        self,
        agent: OpenAIAgentLike,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> RunRecord:
        """Execute an OpenAI agent run with OJS recording.

        In the P1 prototype, this calls the agent's ``run`` or
        ``arun`` method and records the result for later export.

        Args:
            agent: An OpenAI agent instance (or any object with a
                ``run``/``arun`` method).
            messages: Input messages for the agent.
            **kwargs: Additional arguments passed to the agent.

        Returns:
            A RunRecord with the execution details.
        """
        self._run_counter += 1
        run_id = f"run-{self._run_counter}"

        agent_name = getattr(agent, "name", "unknown")

        result = None
        tool_calls: list[dict[str, Any]] = []
        if hasattr(agent, "arun"):
            result = await agent.arun(messages, **kwargs)
        elif hasattr(agent, "run"):
            result = agent.run(messages, **kwargs)
        else:
            raise TypeError(
                f"Agent {agent_name!r} has no 'run' or 'arun' method"
            )

        # Extract tool calls from the result if available
        if self._config.record_tools:
            raw_tool_calls = getattr(result, "tool_calls", None)
            if raw_tool_calls is None and isinstance(result, dict):
                raw_tool_calls = result.get("tool_calls")
            if isinstance(raw_tool_calls, list):
                for tc in raw_tool_calls:
                    if isinstance(tc, dict):
                        tool_calls.append({
                            "name": tc.get("name", "unknown"),
                            "args": tc.get("args", tc.get("arguments", {})),
                            "result": tc.get("result"),
                            "duration_ms": tc.get("duration_ms"),
                        })
                    else:
                        tool_calls.append({
                            "name": getattr(tc, "name", "unknown"),
                            "args": getattr(tc, "args", getattr(tc, "arguments", {})),
                            "result": getattr(tc, "result", None),
                            "duration_ms": getattr(tc, "duration_ms", None),
                        })

        record = RunRecord(
            run_id=run_id,
            agent_name=agent_name,
            messages=messages,
            result=result,
            tool_calls=tool_calls,
        )
        self._runs[run_id] = record
        return record

    async def export_session(self, run_id: str) -> dict[str, Any]:
        """Export a recorded run as an OJS agent envelope.

        Args:
            run_id: The run ID from a previous ``wrap_run`` call.

        Returns:
            A dict representing the OJS job envelope.

        Raises:
            KeyError: If the run_id is not found.
        """
        if run_id not in self._runs:
            raise KeyError(f"Run {run_id!r} not found")

        record = self._runs[run_id]

        return {
            "id": str(uuid.uuid4()),
            "type": self._config.job_type,
            "args": record.messages,
            "meta": {
                "agent_provider": "openai",
                "agent_name": record.agent_name,
                "run_id": record.run_id,
                "tool_call_count": len(record.tool_calls),
            },
            "ext_agent_v2": {
                "provider": "openai",
                "agent_name": record.agent_name,
                "run_id": record.run_id,
                "tool_calls": record.tool_calls,
            },
        }
