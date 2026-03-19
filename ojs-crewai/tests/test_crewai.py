"""Tests for the OJS CrewAI adapter."""

from __future__ import annotations

import asyncio
from typing import Any


class FakeTask:
    """Mock CrewAI task."""

    def __init__(self, description: str = "Do something", agent: Any = None) -> None:
        self.description = description
        self.agent = agent
        self.output = None


class FakeAgent:
    """Mock CrewAI agent."""

    def __init__(self, role: str = "researcher") -> None:
        self.role = role


class FakeCrew:
    """Mock CrewAI crew for testing."""

    def __init__(
        self,
        tasks: list[Any] | None = None,
        output: Any = None,
    ) -> None:
        self.tasks = tasks or []
        self._output = output or "crew result"
        self.kickoff_count = 0

    def kickoff(self, inputs: dict[str, Any] | None = None) -> Any:
        self.kickoff_count += 1
        return self._output


class AsyncFakeCrew:
    """Mock CrewAI crew with async kickoff."""

    def __init__(self, output: Any = None) -> None:
        self.tasks = []
        self._output = output or "async result"

    async def kickoff_async(self, inputs: dict[str, Any] | None = None) -> Any:
        return self._output


class NoKickoffCrew:
    """Mock crew with no kickoff method."""

    tasks = []


def test_wrap_crew_sync() -> None:
    """wrap_crew should work with sync kickoff."""
    from ojs_crewai import CrewAIAdapter, AdapterConfig

    config = AdapterConfig(ojs_url="http://test:8080")
    adapter = CrewAIAdapter(config)
    crew = FakeCrew(output="done")

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))
    result = loop.run_until_complete(durable.kickoff())

    assert result == "done"
    assert crew.kickoff_count == 1
    assert durable.record.crew_id == "crew-1"


def test_wrap_crew_async() -> None:
    """wrap_crew should work with async kickoff_async."""
    from ojs_crewai import CrewAIAdapter

    adapter = CrewAIAdapter()
    crew = AsyncFakeCrew(output="async done")

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))
    result = loop.run_until_complete(durable.kickoff())

    assert result == "async done"


def test_wrap_crew_no_method() -> None:
    """wrap_crew should raise TypeError for crews without kickoff."""
    from ojs_crewai import CrewAIAdapter

    adapter = CrewAIAdapter()
    crew = NoKickoffCrew()

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))

    try:
        loop.run_until_complete(durable.kickoff())
        assert False, "Expected TypeError"
    except TypeError as e:
        assert "no 'kickoff'" in str(e)


def test_task_recording() -> None:
    """Tasks should be recorded with agent roles and execution order."""
    from ojs_crewai import CrewAIAdapter

    adapter = CrewAIAdapter()
    agent = FakeAgent(role="writer")
    task = FakeTask(description="Write a report", agent=agent)
    crew = FakeCrew(tasks=[task], output="report done")

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))
    loop.run_until_complete(durable.kickoff())

    assert len(durable.record.tasks) == 1
    assert durable.record.tasks[0].task_name == "Write a report"
    assert durable.record.tasks[0].agent_role == "writer"
    assert durable.record.tasks[0].execution_order == 1
    assert durable.record.tasks[0].started_at != ""
    assert durable.record.tasks[0].finished_at != ""


def test_to_ojs_envelope() -> None:
    """to_ojs_envelope should produce a valid OJS envelope with ext_agent_v2."""
    from ojs_crewai import CrewAIAdapter, AdapterConfig

    config = AdapterConfig(job_type="agent.custom")
    adapter = CrewAIAdapter(config)
    agent = FakeAgent(role="analyst")
    task = FakeTask(description="Analyze data", agent=agent)
    crew = FakeCrew(tasks=[task])

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))
    loop.run_until_complete(durable.kickoff())

    envelope = durable.to_ojs_envelope()

    assert "id" in envelope
    assert envelope["meta"]["agent_provider"] == "crewai"
    assert envelope["meta"]["task_count"] == 1
    assert envelope["meta"]["agents"] == ["analyst"]
    assert envelope["workflow"]["chain"][0]["args"] == ["Analyze data"]
    assert envelope["workflow"]["chain"][0]["meta"]["execution_order"] == 1

    ext = envelope["ext_agent_v2"]
    assert ext["provider"] == "crewai"
    assert len(ext["task_results"]) == 1
    assert ext["task_results"][0]["task_name"] == "Analyze data"
    assert ext["task_results"][0]["agent_role"] == "analyst"
    assert ext["task_results"][0]["execution_order"] == 1
    assert ext["agents"] == ["analyst"]


def test_envelope_no_tasks() -> None:
    """Envelope with no tasks should have workflow=None."""
    from ojs_crewai import CrewAIAdapter

    adapter = CrewAIAdapter()
    crew = FakeCrew(tasks=[], output="empty")

    loop = asyncio.get_event_loop()
    durable = loop.run_until_complete(adapter.wrap_crew(crew))
    loop.run_until_complete(durable.kickoff())

    envelope = durable.to_ojs_envelope()
    assert envelope["workflow"] is None
