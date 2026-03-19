# OJS LangGraph Adapter

Durable agent execution for [LangGraph](https://langchain-ai.github.io/langgraph/) via OpenJobSpec.

## Installation

```bash
pip install ojs-langgraph
```

## Quick Start

```python
from langgraph.graph import StateGraph, START
from ojs_langgraph import durable

# Build your LangGraph
graph = StateGraph(dict)
graph.add_node("process", lambda state: {"result": "done"})
graph.add_edge(START, "process")
compiled = graph.compile()

# Wrap with OJS durability
durable_graph = durable(compiled, ojs_url="http://localhost:8080")

# Use exactly like a normal LangGraph
result = await durable_graph.ainvoke({"query": "hello"})
```

## Features

- **Durable execution**: Agent state persisted in OJS memory DAG
- **Fork/merge**: Create parallel conversation branches
- **Human-in-the-loop**: Pause/resume for human approval
- **Tool retry**: Retry failed tools with alternate providers
- **Deterministic replay**: Reproduce agent executions

## API

### `durable(graph, *, ojs_url, job_type, checkpoint_every, policy)`

Wraps a compiled LangGraph with OJS durability. Returns a `DurableGraph`
with the same `ainvoke()` interface.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `graph` | compiled graph | required | LangGraph compiled StateGraph |
| `ojs_url` | str | `http://localhost:8080` | OJS server URL |
| `job_type` | str | `agent.langgraph` | OJS job type |
| `checkpoint_every` | int | 1 | Checkpoint frequency |
| `policy` | dict | None | Execution policy |
