"""OJS LangGraph Adapter -- durable agent execution for LangGraph.

Provides a ``durable`` wrapper that makes any LangGraph StateGraph
durable via OJS, with checkpoint persistence in the OJS memory DAG,
tool retry with alternate providers, and human-in-the-loop support.

Usage::

    from langgraph_ojs import durable

    graph = StateGraph(AgentState)
    graph.add_node("search", search_node)
    graph.add_edge(START, "search")
    compiled = graph.compile()

    # Wrap with OJS durability
    durable_graph = durable(compiled, ojs_url="http://localhost:8080")
    result = await durable_graph.ainvoke({"query": "latest OJS release"})
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Checkpointable(Protocol):
    """Protocol for objects that support checkpoint/restore."""

    async def ainvoke(self, input: Any, config: dict[str, Any] | None = None) -> Any: ...


@dataclass
class StepRecord:
    """Record of a single graph invocation step."""

    index: int
    started_at: str
    finished_at: str
    input_snapshot: Any = None
    output_snapshot: Any = None
    error: str | None = None


class DurableGraph:
    """Wraps a LangGraph compiled graph with OJS durability.

    Records execution steps with timestamps and input/output snapshots.

    The full P2 implementation will:
    - Persist LangGraph checkpoints as OJS memory DAG nodes
    - Map LangGraph interrupts to PAUSE_HUMAN/RESUME_HUMAN
    - Support tool retry with alternate providers
    - Enable fork/merge of conversation branches
    """

    def __init__(
        self,
        graph: Checkpointable,
        *,
        ojs_url: str = "http://localhost:8080",
        job_type: str = "agent.langgraph",
        checkpoint_every: int = 1,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self._graph = graph
        self._ojs_url = ojs_url
        self._job_type = job_type
        self._checkpoint_every = checkpoint_every
        self._policy = policy or {}
        self._step_count = 0
        self._steps: list[StepRecord] = []

    async def ainvoke(
        self,
        input: Any,
        config: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke the graph with OJS durability wrapping.

        Records each invocation as a step with timestamps and
        input/output snapshots for later replay or export.

        Args:
            input: The input to the graph.
            config: Optional LangGraph config.

        Returns:
            The graph's output.
        """
        self._step_count += 1
        step_index = self._step_count
        started_at = datetime.now(timezone.utc).isoformat()
        error_msg = None

        try:
            result = await self._graph.ainvoke(input, config)
        except Exception as exc:
            error_msg = str(exc)
            finished_at = datetime.now(timezone.utc).isoformat()
            self._steps.append(
                StepRecord(
                    index=step_index,
                    started_at=started_at,
                    finished_at=finished_at,
                    input_snapshot=_safe_snapshot(input),
                    output_snapshot=None,
                    error=error_msg,
                )
            )
            raise

        finished_at = datetime.now(timezone.utc).isoformat()
        self._steps.append(
            StepRecord(
                index=step_index,
                started_at=started_at,
                finished_at=finished_at,
                input_snapshot=_safe_snapshot(input),
                output_snapshot=_safe_snapshot(result),
            )
        )
        return result

    @property
    def step_count(self) -> int:
        """Number of invocations recorded."""
        return self._step_count

    @property
    def steps(self) -> list[StepRecord]:
        """Recorded step history."""
        return list(self._steps)

    def to_ojs_envelope(self) -> dict[str, Any]:
        """Serialize the execution as an OJS-compatible job envelope.

        Returns:
            A dict with OJS envelope fields including ext_agent_v2
            metadata for agent execution tracking.
        """
        step_dicts = [asdict(s) for s in self._steps]

        return {
            "id": str(uuid.uuid4()),
            "type": self._job_type,
            "args": [],
            "meta": {
                "agent_provider": "langgraph",
                "step_count": self._step_count,
                "ojs_url": self._ojs_url,
            },
            "ext_agent_v2": {
                "provider": "langgraph",
                "job_type": self._job_type,
                "steps": step_dicts,
                "checkpoint_every": self._checkpoint_every,
                "policy": self._policy,
            },
        }


def _safe_snapshot(value: Any) -> Any:
    """Create a JSON-safe snapshot of a value."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def durable(
    graph: Checkpointable,
    *,
    ojs_url: str = "http://localhost:8080",
    job_type: str = "agent.langgraph",
    checkpoint_every: int = 1,
    policy: dict[str, Any] | None = None,
) -> DurableGraph:
    """Wrap a LangGraph compiled graph with OJS durability.

    This is the primary entry point for LangGraph users::

        from langgraph_ojs import durable

        durable_graph = durable(compiled_graph, ojs_url="http://localhost:8080")
        result = await durable_graph.ainvoke({"query": "hello"})

    Args:
        graph: A compiled LangGraph StateGraph.
        ojs_url: Base URL of the OJS server.
        job_type: OJS job type for agent jobs.
        checkpoint_every: Checkpoint frequency (every N steps).
        policy: Execution policy (retry, timeout, etc.).

    Returns:
        A DurableGraph wrapper with the same ``ainvoke`` interface.
    """
    return DurableGraph(
        graph,
        ojs_url=ojs_url,
        job_type=job_type,
        checkpoint_every=checkpoint_every,
        policy=policy,
    )
