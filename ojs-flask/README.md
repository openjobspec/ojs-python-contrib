# ojs-flask

Flask integration for [Open Job Spec (OJS)](https://github.com/openjobspec/spec) — a universal, language-agnostic standard for background job processing.

## Installation

```bash
pip install openjobspec-flask
```

## Quickstart

### Initialize the Extension

Use the standard Flask extension pattern — either direct initialization or the `init_app` factory:

```python
from flask import Flask
from ojs_flask import OJS

# Direct initialization
app = Flask(__name__)
app.config["OJS_URL"] = "http://localhost:8080"
ojs = OJS(app)

# Or, with the application factory pattern
ojs = OJS()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["OJS_URL"] = "http://localhost:8080"
    ojs.init_app(app)
    return app
```

### Enqueue Jobs from Route Handlers

```python
from flask import request
from ojs_flask import enqueue


@app.post("/emails")
def send_email() -> tuple[dict[str, str], int]:
    data: dict[str, str] = request.get_json()
    job = enqueue(
        "email.send",
        [data["to"], data["subject"], data["body"]],
        queue="email",
    )
    return {"job_id": job.id}, 202
```

Or use the extension instance directly:

```python
@app.post("/reports")
def generate_report() -> tuple[dict[str, str], int]:
    job = ojs.enqueue("report.generate", [request.json["type"]], queue="reports")
    return {"job_id": job.id}, 202
```

### Worker Integration

Workers run separately from your Flask application using the OJS Python SDK directly:

```python
import asyncio
import ojs

worker = ojs.Worker("http://localhost:8080", queues=["email", "reports"])


@worker.register("email.send")
async def handle_email(ctx: ojs.JobContext):
    to, subject, body = ctx.args
    await send_email(to, subject, body)


@worker.register("report.generate")
async def handle_report(ctx: ojs.JobContext):
    report_type = ctx.args[0]
    await generate_report(report_type)


if __name__ == "__main__":
    asyncio.run(worker.start())
```

## Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `OJS_URL` | `http://localhost:8080` | OJS server base URL |
| `OJS_QUEUES` | `["default"]` | Default queue names for workers |

## API Reference

### `OJS(app=None)`

Flask extension class. Call `init_app(app)` or pass the app to the constructor.

- **`client`** — property returning the `ojs.SyncClient` from the current app context.
- **`enqueue(job_type, args, **kwargs)`** — enqueue a job via the current app client.

### `enqueue(job_type, args, **kwargs)`

Module-level helper that retrieves the client from `current_app` and enqueues a job.

### `get_client()`

Returns the `ojs.SyncClient` from the current Flask application context.

## License

Apache-2.0
