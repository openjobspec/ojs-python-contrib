# openjobspec-celery

Celery compatibility layer for [Open Job Spec (OJS)](https://github.com/openjobspec/openjobspec) — migrate from Celery to OJS with minimal code changes.

## Installation

```bash
pip install openjobspec-celery
```

## Quick Start: Drop-in `@ojs_task` Replacement

Replace `@celery.task` with `@ojs_task` and keep the same `.delay()` / `.apply_async()` API you already know.

### Before (Celery)

```python
from celery import Celery

app = Celery("myapp", broker="redis://localhost:6379")

@app.task(name="email.send")
def send_email(to: str, subject: str, body: str) -> None:
    # send the email
    print(f"Sending email to {to}")

@app.task(name="report.generate", bind=True, max_retries=3)
def generate_report(self, report_id: int) -> None:
    try:
        # generate report
        print(f"Generating report {report_id}")
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

# Enqueue tasks
send_email.delay("user@example.com", "Hello", "World")
generate_report.apply_async(args=[42], queue="reports", countdown=300)
```

### After (OJS via Celery Adapter)

```python
from ojs_celery import OJSAdapter

adapter = OJSAdapter(ojs_url="http://localhost:8080")

@adapter.task(name="email.send")
def send_email(to: str, subject: str, body: str) -> None:
    print(f"Sending email to {to}")

@adapter.task(name="report.generate")
def generate_report(report_id: int) -> None:
    print(f"Generating report {report_id}")

# Same API — works identically
send_email.delay("user@example.com", "Hello", "World")
generate_report.apply_async(args=[42], queue="reports", countdown=300)
```

## Side-by-Side Comparison

| Celery | OJS Celery Adapter | Notes |
|---|---|---|
| `@app.task(name="x")` | `@adapter.task(name="x")` | Same decorator pattern |
| `task.delay(*args)` | `task.delay(*args)` | Identical call signature |
| `task.apply_async(args=[], queue=...)` | `task.apply_async(args=[], queue=...)` | Queue mapping preserved |
| `countdown=60` | `countdown=60` | Converted to `delay_until` |
| `max_retries=3` | OJS retry policy | Configured server-side |
| `bind=True` (access `self`) | `ojs.JobContext` | Via OJS worker handlers |
| Redis/RabbitMQ broker | OJS server (HTTP) | Vendor-neutral backend |

## Full Celery-Compatible App Interface

For larger migrations, use `CeleryCompat` which provides a full Celery-app-like interface:

```python
from ojs_celery.compat import CeleryCompat

app = CeleryCompat(ojs_url="http://localhost:8080")

@app.task(name="order.process")
def process_order(order_id: int) -> None:
    print(f"Processing order {order_id}")

# Dynamic dispatch (no decorator needed)
app.send_task("order.process", args=[42], queue="orders")
```

## Migration Helpers

Scan your existing Celery app to generate a migration report:

```python
from ojs_celery.migration import scan_celery_tasks, migrate_task

# Scan all registered tasks
report = scan_celery_tasks(celery_app)
for task_info in report:
    print(f"{task_info['name']} → queue={task_info['queue']}, retries={task_info['max_retries']}")

# Wrap an existing Celery task for OJS
ojs_task = migrate_task(celery_app.tasks["email.send"])
ojs_task.delay("user@example.com", "Hello", "World")
```

> **Note:** Migration helpers require Celery to be installed. The core adapter and compat modules work without Celery.

## Running the Examples

```bash
cd examples/
docker compose up -d          # Start Redis + OJS server
pip install -r requirements.txt
python before_celery.py       # See original Celery code
python after_ojs.py           # See migrated OJS code
```

## License

Apache-2.0
