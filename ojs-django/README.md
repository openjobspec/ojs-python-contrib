# openjobspec-django

Django integration for [Open Job Spec (OJS)](https://github.com/openjobspec/openjobspec) — a universal, language-agnostic standard for background job processing.

## Installation

```bash
pip install openjobspec-django
```

## Quick Start

### 1. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "ojs_django",
]

OJS_URL = "http://localhost:8080"
OJS_QUEUES = ["default", "email"]
```

### 2. Define job handlers

```python
# myapp/jobs.py
import ojs
from ojs_django import ojs_job

@ojs_job("email.send")
async def handle_email_send(ctx: ojs.JobContext) -> dict:
    to = ctx.args[0]
    template = ctx.args[1]
    await send_email(to, template)
    return {"sent_to": to}
```

### 3. Enqueue jobs from views

```python
# myapp/views.py
from django.db import transaction
from ojs_django import enqueue_after_commit

def create_user(request):
    with transaction.atomic():
        user = User.objects.create(email=request.POST["email"])
        # Job is only sent to the OJS server if the transaction commits
        enqueue_after_commit(
            "email.send",
            [user.email, "welcome"],
            queue="email",
        )
    return JsonResponse({"id": user.id})
```

### 4. Run the worker

```bash
python manage.py ojs_worker
```

## Configuration

All settings are read from your Django `settings.py`:

| Setting | Default | Description |
|---|---|---|
| `OJS_URL` | `"http://localhost:8080"` | OJS server base URL |
| `OJS_QUEUES` | `["default"]` | Queue names for the worker to consume |
| `OJS_CONCURRENCY` | `10` | Maximum concurrent job executions |
| `OJS_POLL_INTERVAL` | `2.0` | Seconds between poll requests when idle |

## API Reference

### `@ojs_job(job_type)`

Decorator that registers an async function as a handler for the given job type. The function receives an `ojs.JobContext` with access to `.job_id`, `.job_type`, `.args`, `.meta`, and `.attempt`.

```python
@ojs_job("report.generate")
async def handle_report(ctx: ojs.JobContext) -> dict:
    report_type = ctx.args[0]
    return generate_report(report_type)
```

### `enqueue_after_commit(job_type, args, *, queue, meta, using, **kwargs)`

Enqueues a job only after the current database transaction commits. Uses `django.db.transaction.on_commit()` internally, so the job is **never sent** if the transaction rolls back.

```python
from ojs_django import enqueue_after_commit

with transaction.atomic():
    order = Order.objects.create(...)
    enqueue_after_commit("order.process", [str(order.id)], queue="orders")
```

Parameters:
- `job_type` — Dot-namespaced job type (e.g., `"email.send"`)
- `args` — Positional arguments for the job handler (JSON-serializable list)
- `queue` — Target queue name (default: `"default"`)
- `meta` — Key-value metadata dict (default: `None`)
- `using` — Database alias for the transaction (default: `"default"`)

### `enqueue(job_type, args, *, queue, meta, **kwargs)`

Enqueues a job immediately, without waiting for any transaction. Useful outside of request/transaction context.

```python
from ojs_django import enqueue

enqueue("cleanup.old_sessions", [], queue="maintenance")
```

### `get_client()`

Returns a lazily-initialized, process-wide `ojs.SyncClient` instance configured from Django settings.

```python
from ojs_django import get_client

client = get_client()
job = client.enqueue("ping", [])
```

### Management Command: `ojs_worker`

```bash
# Use settings from OJS_QUEUES and OJS_CONCURRENCY
python manage.py ojs_worker

# Override via CLI
python manage.py ojs_worker --queues email,notifications --concurrency 20
```

| Argument | Description |
|---|---|
| `--queues` | Comma-separated queue names (overrides `OJS_QUEUES`) |
| `--concurrency` | Max concurrent jobs (overrides `OJS_CONCURRENCY`) |

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy src/
```

## License

Apache-2.0
