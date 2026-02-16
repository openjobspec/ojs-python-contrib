"""Original application using Celery.

This shows a typical Celery setup with task definitions and enqueue calls.
See after_ojs.py for the migrated version using the OJS Celery adapter.
"""

# NOTE: This file is for illustration only. Running it requires a Celery
# broker (Redis/RabbitMQ) and a Celery worker process.

from celery import Celery

app = Celery("myapp", broker="redis://localhost:6379/0")

# Configure default queue and retry settings
app.conf.task_default_queue = "default"
app.conf.task_acks_late = True


@app.task(name="email.send")
def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email notification."""
    print(f"Sending email to {to}: {subject}")
    return {"status": "sent", "to": to}


@app.task(name="report.generate", bind=True, max_retries=3)
def generate_report(self, report_id: int, format: str = "pdf") -> dict:
    """Generate a report with retry support."""
    try:
        print(f"Generating {format} report #{report_id}")
        return {"report_id": report_id, "format": format, "status": "complete"}
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@app.task(name="data.cleanup", queue="maintenance")
def cleanup_old_data(days: int = 30) -> dict:
    """Clean up data older than N days."""
    print(f"Cleaning up data older than {days} days")
    return {"deleted_count": 42}


if __name__ == "__main__":
    # Enqueue tasks using Celery's API
    print("=== Celery Task Enqueue Examples ===\n")

    # Simple .delay() call
    print("1. send_email.delay(...)")
    print(f"   Would call: send_email.delay('user@example.com', 'Welcome', 'Hello!')\n")

    # .apply_async() with queue and countdown
    print("2. generate_report.apply_async(...)")
    print(f"   Would call: generate_report.apply_async(args=[42], queue='reports', countdown=300)\n")

    # Task on a specific queue
    print("3. cleanup_old_data.delay(...)")
    print(f"   Would call: cleanup_old_data.delay(90)\n")

    print("NOTE: This example requires a running Celery broker and worker.")
    print("See after_ojs.py for the OJS equivalent that uses HTTP instead.")
