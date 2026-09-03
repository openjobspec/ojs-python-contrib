# openjobspec-django

Django integration for [Open Job Spec (OJS)](https://github.com/openjobspec/spec) — a universal, language-agnostic standard for background job processing.

**Status:** Beta — API is stable and suitable for production use with non-critical workloads.

## Installation

```bash
pip install openjobspec-django
```

Requires Django 4.2+ and Python 3.11+.

## Quick Start

### 1. Add to INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "ojs_django",
]

OJS = {
    "URL": "http://localhost:8080",
    "DEFAULT_QUEUE": "default",
    "WORKER": {
        "concurrency": 10,
        "queues": ["default", "email"],
    },
}
```

### 2. Define job handlers

```python
# myapp/jobs.py
import ojs
from ojs_django import ojs_job


@ojs_job("email.send", queue="email", retry=ojs.RetryPolicy(max_attempts=3))
async def send_welcome_email(ctx: ojs.JobContext) -> dict:
    user_id = ctx.args[0]
    template = ctx.args[1]
    await send_email(user_id, template)
    return {"sent_to": user_id}
```

Job modules (`jobs.py`) are **auto-discovered** from all installed apps on startup.

### 3. Enqueue jobs from views

```python
# myapp/views.py
from django.db import transaction
from ojs_django import enqueue, enqueue_after_commit


def create_user(request):
    with transaction.atomic():
        user = User.objects.create(email=request.POST["email"])
        # Job is only sent if the transaction commits
        enqueue_after_commit(
            "email.send",
            [user.id, "welcome"],
            queue="email",
        )
    return JsonResponse({"id": user.id})


# Or use the decorator's .enqueue() shortcut:
from myapp.jobs import send_welcome_email


def create_user_v2(request):
    user = User.objects.create(email=request.POST["email"])
    send_welcome_email.enqueue(user.id, "welcome")
    return JsonResponse({"id": user.id})
```

### 4. Run the worker

```bash
python manage.py ojs_worker
```

## Configuration

All settings are read from the `OJS` dict in `settings.py`:

```python
OJS = {
    # OJS server URL
    "URL": "http://localhost:8080",
    # Default queue for enqueued jobs
    "DEFAULT_QUEUE": "default",
    # Optional prefix for all queue names (useful for multi-tenant)
    "QUEUE_PREFIX": "",
    # Default retry policy applied to all jobs unless overridden
    "DEFAULT_RETRY": {
        "max_attempts": 5,
        "backoff": "exponential",
    },
    # Worker-specific settings
    "WORKER": {
        "concurrency": 10,
        "queues": ["default", "email"],
        "poll_interval": 2.0,
    },
}
```

### Legacy flat settings

For backward compatibility, flat settings are also supported:

```python
OJS_URL = "http://localhost:8080"
OJS_QUEUES = ["default"]
OJS_CONCURRENCY = 10
OJS_POLL_INTERVAL = 2.0
```

## API Reference

### `@ojs_job(job_type, *, queue, retry, priority, tags)`

Decorator that registers an async function as a handler and adds `.enqueue()` / `.enqueue_after_commit()` methods:

```python
@ojs_job(
    "report.generate",
    queue="reports",
    retry=ojs.RetryPolicy(max_attempts=5),
    priority=10,
    tags=["critical"],
)
async def handle_report(ctx: ojs.JobContext) -> dict:
    report_type = ctx.args[0]
    return generate_report(report_type)


# Enqueue via the decorator
handle_report.enqueue("monthly")

# Enqueue after transaction commit
with transaction.atomic():
    obj = MyModel.objects.create(...)
    handle_report.enqueue_after_commit("monthly", using="default")
```

### `enqueue(job_type, *args, **options)`

Enqueue a job immediately:

```python
from ojs_django import enqueue

job = enqueue("email.send", "user@test.com", "welcome", queue="email")
```

### `enqueue_at(job_type, scheduled_at, *args, **options)`

Enqueue a job for future execution:

```python
from datetime import datetime, timezone, timedelta
from ojs_django import enqueue_at

run_at = datetime.now(timezone.utc) + timedelta(hours=1)
job = enqueue_at("report.generate", run_at, "monthly")
```

### `enqueue_batch(jobs)`

Enqueue multiple jobs atomically:

```python
from ojs_django import enqueue_batch

jobs = enqueue_batch(
    [
        {"type": "email.send", "args": ["a@b.com", "welcome"]},
        {"type": "email.send", "args": ["c@d.com", "welcome"], "queue": "bulk"},
    ]
)
```

### `enqueue_after_commit(job_type, args, *, queue, meta, using)`

Enqueue a job only after the current database transaction commits:

```python
from ojs_django import enqueue_after_commit

with transaction.atomic():
    order = Order.objects.create(...)
    enqueue_after_commit("order.process", [str(order.id)], queue="orders")
```

### `get_client()`

Returns a lazily-initialized, process-wide `ojs.SyncClient`:

```python
from ojs_django import get_client

client = get_client()
job = client.enqueue("ping", [])
```

## Management Commands

### `ojs_worker` — Start a worker

```bash
# Use settings from OJS["WORKER"]
python manage.py ojs_worker

# Override via CLI
python manage.py ojs_worker --queues email,notifications --concurrency 20
```

| Argument | Description |
|---|---|
| `--queues` | Comma-separated queue names (overrides config) |
| `--concurrency` | Max concurrent jobs (overrides config) |

### `ojs_status` — Check server status

```bash
# Human-readable output
python manage.py ojs_status

# Specific queue
python manage.py ojs_status --queue email

# JSON output (for scripting)
python manage.py ojs_status --json
```

### `ojs_purge` — Purge dead letter queue

```bash
# Preview what would be deleted
python manage.py ojs_purge --dry-run

# Delete all dead letter jobs
python manage.py ojs_purge

# Delete from specific queue only
python manage.py ojs_purge --queue email --limit 50
```

## Middleware

Add `OJSMiddleware` to automatically propagate request context to jobs:

```python
MIDDLEWARE = [
    # ...
    "ojs_django.middleware.OJSMiddleware",
    # ...
]
```

This adds to each request:
- `request.ojs_request_id` — Extracted from `X-Request-ID` / `X-Correlation-ID` headers, or auto-generated
- `request.ojs_meta` — Dict with `request_id`, `user_id`, `username` (if authenticated)

Access the current request context from anywhere:

```python
from ojs_django.middleware import get_current_ojs_meta, get_current_request_id

meta = get_current_ojs_meta()  # Returns None outside request context
```

## Admin Integration

OJS admin views are registered automatically. Access them at `/admin/ojs/`:

- **Dashboard** — Server health and queue overview
- **Queues** — Queue statistics and details
- **Dead Letter** — Browse and paginate dead-letter jobs

All views are read-only (data comes from the OJS server, not Django models).

## Migration Guide from Celery

| Celery | ojs_django |
|---|---|
| `@shared_task` | `@ojs_job("task.name")` |
| `task.delay(arg1, arg2)` | `handler.enqueue(arg1, arg2)` |
| `task.apply_async(args=[...], countdown=60)` | `enqueue_at("task.name", now + timedelta(seconds=60), ...)` |
| `task.apply_async(args=[...], queue="q")` | `handler.enqueue(arg1, queue="q")` |
| `celery -A proj worker` | `python manage.py ojs_worker` |
| `CELERY_BROKER_URL` | `OJS["URL"]` |
| `CELERY_TASK_QUEUES` | `OJS["WORKER"]["queues"]` |
| `CELERY_WORKER_CONCURRENCY` | `OJS["WORKER"]["concurrency"]` |

### Key differences

1. **No broker** — OJS uses a dedicated job server (Redis or Postgres backed), not a message broker.
2. **Args are a list** — Job arguments are passed as a JSON-serializable list via `ctx.args`, not `*args/**kwargs`.
3. **Async handlers** — All job handlers are `async def`. Use `sync_to_async` for synchronous code.
4. **Transactions** — Use `enqueue_after_commit()` instead of Celery's `transaction.on_commit()` pattern.

## Development

```bash
pip install -e ".[dev]"
PYTHONPATH=. pytest
ruff check src/
mypy src/
```

## License

Apache-2.0
