# OJS CrewAI Adapter

OJS durability layer for [CrewAI](https://www.crewai.com/), mapping crew tasks to OJS workflow chains for persistence, replay, and monitoring.

## Installation

```bash
pip install ojs-crewai
```

## Quick Start

```python
from crewai import Agent, Task, Crew
from ojs_crewai import CrewAIAdapter, AdapterConfig

config = AdapterConfig(ojs_url="http://localhost:8080")
adapter = CrewAIAdapter(config)

# Wrap any CrewAI crew with OJS durability
durable_crew = await adapter.wrap_crew(crew)
result = await durable_crew.kickoff()

# Export as OJS envelope with workflow chain
envelope = durable_crew.to_ojs_envelope()
```

## Features

- **Durable execution**: Crew runs persisted as OJS job envelopes
- **Task → chain mapping**: Crew tasks mapped to OJS workflow chains
- **Agent role tracking**: Records which agent handled each task
- **Replay**: Reproduce crew executions from OJS state

## API

### `AdapterConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ojs_url` | str | `http://localhost:8080` | OJS server URL |
| `job_type` | str | `agent.crewai` | OJS job type for crew runs |
| `map_tasks_to_chain` | bool | `True` | Map tasks to OJS workflow chains |

### `CrewAIAdapter`

| Method | Description |
|--------|-------------|
| `wrap_crew(crew)` | Make a crew durable via OJS |

### `DurableCrew`

| Method | Description |
|--------|-------------|
| `kickoff(inputs=None)` | Kick off the crew with OJS recording |
| `to_ojs_envelope()` | Export run as OJS envelope with workflow chain |
| `record` | Access the recorded crew execution |
