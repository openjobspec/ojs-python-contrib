"""OJS adapter for CrewAI.

Wraps CrewAI crews with OJS durability, mapping crew tasks to OJS
workflow chains for persistence, replay, and monitoring.

Usage::

    from ojs_crewai import CrewAIAdapter, AdapterConfig

    config = AdapterConfig(ojs_url="http://localhost:8080")
    adapter = CrewAIAdapter(config)

    durable_crew = await adapter.wrap_crew(crew)
    result = await durable_crew.kickoff()
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CrewLike(Protocol):
    """Protocol for objects that behave like a CrewAI Crew."""

    def kickoff(self, **kwargs: Any) -> Any: ...


@dataclass
class AdapterConfig:
    """Configuration for the CrewAI → OJS adapter.

    Attributes:
        ojs_url: Base URL of the OJS server.
        job_type: OJS job type for crew runs.
        map_tasks_to_chain: Whether to map crew tasks to OJS workflow chains.
    """

    ojs_url: str = "http://localhost:8080"
    job_type: str = "agent.crewai"
    map_tasks_to_chain: bool = True


@dataclass
class TaskRecord:
    """Record of a single crew task execution.

    Attributes:
        task_name: Name/description of the task.
        agent_role: Role of the agent that executed this task.
        result: Task output.
        execution_order: Position in the execution sequence (1-based).
        started_at: ISO-8601 timestamp when execution started.
        finished_at: ISO-8601 timestamp when execution finished.
    """

    task_name: str
    agent_role: str
    result: Any = None
    execution_order: int = 0
    started_at: str = ""
    finished_at: str = ""


@dataclass
class CrewRecord:
    """Record of a full crew execution.

    Attributes:
        crew_id: Unique identifier for this crew run.
        tasks: Recorded task executions.
        result: Final crew output.
    """

    crew_id: str
    tasks: list[TaskRecord] = field(default_factory=list)
    result: Any = None


class DurableCrew:
    """A crew wrapped with OJS durability.

    Records each task execution and maps the crew's task pipeline
    to an OJS workflow chain.
    """

    def __init__(
        self,
        crew: CrewLike,
        config: AdapterConfig,
        crew_id: str,
    ) -> None:
        self._crew = crew
        self._config = config
        self._crew_id = crew_id
        self._record = CrewRecord(crew_id=crew_id)

    async def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        """Kick off the crew with OJS recording.

        In the P1 prototype, this passes through to the underlying
        crew and records the result.

        Args:
            inputs: Optional inputs for the crew.

        Returns:
            The crew's output.
        """
        kwargs: dict[str, Any] = {}
        if inputs is not None:
            kwargs["inputs"] = inputs

        if hasattr(self._crew, "kickoff_async"):
            result = await self._crew.kickoff_async(**kwargs)
        elif hasattr(self._crew, "kickoff"):
            result = self._crew.kickoff(**kwargs)
        else:
            raise TypeError(
                "Crew object has no 'kickoff' or 'kickoff_async' method"
            )

        self._record.result = result

        # Record individual tasks with execution order
        tasks = getattr(self._crew, "tasks", [])
        for order, task in enumerate(tasks, start=1):
            task_name = getattr(task, "description", "unknown")
            agent = getattr(task, "agent", None)
            agent_role = getattr(agent, "role", "unknown") if agent else "unknown"
            now = datetime.now(timezone.utc).isoformat()
            self._record.tasks.append(
                TaskRecord(
                    task_name=task_name,
                    agent_role=agent_role,
                    result=getattr(task, "output", None),
                    execution_order=order,
                    started_at=now,
                    finished_at=now,
                )
            )

        return result

    def to_ojs_envelope(self) -> dict[str, Any]:
        """Export the crew run as an OJS job envelope.

        Returns:
            A dict representing the OJS job envelope with workflow
            chain mapping, ext_agent_v2 metadata, and task results.
        """
        chain_steps = [
            {
                "type": f"{self._config.job_type}.task",
                "args": [t.task_name],
                "meta": {
                    "agent_role": t.agent_role,
                    "execution_order": t.execution_order,
                },
            }
            for t in self._record.tasks
        ]

        # Collect agent metadata from tasks
        agents = list({t.agent_role for t in self._record.tasks if t.agent_role != "unknown"})

        task_results = [
            {
                "task_name": t.task_name,
                "agent_role": t.agent_role,
                "execution_order": t.execution_order,
                "result": str(t.result) if t.result is not None else None,
                "started_at": t.started_at,
                "finished_at": t.finished_at,
            }
            for t in self._record.tasks
        ]

        crew_name = getattr(self._crew, "name", None) or self._config.job_type

        return {
            "id": str(uuid.uuid4()),
            "type": crew_name,
            "args": [],
            "meta": {
                "agent_provider": "crewai",
                "crew_id": self._crew_id,
                "task_count": len(self._record.tasks),
                "agents": agents,
            },
            "workflow": {"chain": chain_steps} if chain_steps else None,
            "ext_agent_v2": {
                "provider": "crewai",
                "crew_name": crew_name,
                "crew_id": self._crew_id,
                "task_results": task_results,
                "agents": agents,
            },
        }

    @property
    def record(self) -> CrewRecord:
        """Access the recorded crew execution."""
        return self._record


class CrewAIAdapter:
    """Wraps CrewAI crews with OJS durability.

    This P1 prototype records crew executions and maps crew tasks
    to OJS workflow chains. The full P2 implementation will persist
    state to the OJS server and support pause/resume.
    """

    def __init__(self, config: AdapterConfig | None = None) -> None:
        self._config = config or AdapterConfig()
        self._crew_counter = 0

    async def wrap_crew(self, crew: CrewLike) -> DurableCrew:
        """Make a CrewAI crew durable via OJS.

        Maps crew tasks to OJS workflow chains and wraps execution
        with recording and persistence.

        Args:
            crew: A CrewAI Crew instance.

        Returns:
            A DurableCrew with the same ``kickoff`` interface.
        """
        self._crew_counter += 1
        crew_id = f"crew-{self._crew_counter}"

        return DurableCrew(
            crew=crew,
            config=self._config,
            crew_id=crew_id,
        )
