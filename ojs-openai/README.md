# OJS OpenAI Agents SDK Adapter

OJS durability layer for the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python), enabling persistence, replay, and cross-provider portability for agent runs.

## Installation

```bash
pip install ojs-openai
```

## Quick Start

```python
from ojs_openai import OpenAIAdapter, AdapterConfig

config = AdapterConfig(ojs_url="http://localhost:8080")
adapter = OpenAIAdapter(config)

# Wrap any OpenAI agent run with OJS durability
record = await adapter.wrap_run(agent, [
    {"role": "user", "content": "What is OJS?"}
])

# Export the run as an OJS envelope
envelope = await adapter.export_session(record.run_id)
```

## Features

- **Durable execution**: Agent runs persisted as OJS job envelopes
- **Replay**: Reproduce agent executions from OJS state
- **Cross-provider portability**: Export sessions in a vendor-neutral format
- **Tool recording**: Optionally capture tool calls in the envelope

## API

### `AdapterConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ojs_url` | str | `http://localhost:8080` | OJS server URL |
| `job_type` | str | `agent.openai` | OJS job type for agent runs |
| `record_tools` | bool | `True` | Record tool calls |

### `OpenAIAdapter`

| Method | Description |
|--------|-------------|
| `wrap_run(agent, messages, **kwargs)` | Execute agent with OJS recording |
| `export_session(run_id)` | Export run as OJS envelope |
