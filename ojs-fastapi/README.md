# openjobspec-fastapi

FastAPI integration for [Open Job Spec (OJS)](https://github.com/openjobspec/openjobspec) —
dependency injection, lifespan-managed workers, and Pydantic model bridging.

## Installation

```bash
pip install openjobspec-fastapi
```

## Quick Start

### Dependency Injection

Use `get_ojs_client` with FastAPI's `Depends()` to inject the OJS client into any endpoint:

```python
from fastapi import Depends, FastAPI
import ojs
from ojs_fastapi import OJSPlugin, get_ojs_client, ojs_lifespan, EnqueueRequest, EnqueueResponse

plugin = OJSPlugin(url="http://localhost:8080")

app = FastAPI()
app.state.ojs_plugin = plugin

@app.post("/jobs", response_model=EnqueueResponse)
async def enqueue_job(
    body: EnqueueRequest,
    client: ojs.Client = Depends(get_ojs_client),
) -> EnqueueResponse:
    job = await client.enqueue(body.type, body.args, queue=body.queue, meta=body.meta)
    return EnqueueResponse(job_id=job.id, type=job.type, state=str(job.state), queue=job.queue)
```

### Lifespan for Worker Startup/Shutdown

Use `ojs_lifespan` to manage the OJS client and worker lifecycle alongside your FastAPI app:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import ojs
from ojs_fastapi import OJSPlugin, ojs_lifespan

plugin = OJSPlugin(url="http://localhost:8080", queues=["default", "emails"])

# Register worker handlers
worker = ojs.Worker(plugin.url, queues=plugin.queues)
plugin._worker = worker

@worker.register("email.send")
async def handle_email(ctx: ojs.JobContext) -> dict:
    to = ctx.args[0]
    print(f"Sending email to {to}")
    return {"sent": True}

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with ojs_lifespan(app, plugin=plugin) as state:
        yield state

app = FastAPI(lifespan=lifespan)
```

### Pydantic Model Bridging

Use the provided Pydantic models for request/response validation:

```python
from ojs_fastapi import EnqueueRequest, EnqueueResponse
from ojs_fastapi.models import JobResponse

# EnqueueRequest fields: type, args, queue, meta, priority
# EnqueueResponse fields: job_id, type, state, queue
# JobResponse fields: job_id, type, state, queue, args, meta, priority, attempt, timestamps, result
```

## Configuration

`OJSPlugin` accepts the following parameters:

| Parameter        | Type         | Default       | Description                    |
|------------------|-------------|---------------|--------------------------------|
| `url`            | `str`        | *(required)*  | OJS server URL                 |
| `queues`         | `list[str]`  | `["default"]` | Queues for the worker to poll  |
| `concurrency`    | `int`        | `10`          | Max concurrent jobs            |
| `poll_interval`  | `float`      | `2.0`         | Seconds between worker polls   |

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src/
```

## License

Apache-2.0
