"""Same application migrated to OJS via the Celery adapter.

Compare with before_celery.py to see the minimal changes required.
Only 3 lines change: the import, the app initialization, and the decorator.
"""

from ojs_celery import OJSAdapter

adapter = OJSAdapter(ojs_url="http://localhost:8080")


@adapter.task(name="email.send")
def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email notification."""
    print(f"Sending email to {to}: {subject}")
    return {"status": "sent", "to": to}


@adapter.task(name="report.generate")
def generate_report(report_id: int, format: str = "pdf") -> dict:
    """Generate a report."""
    print(f"Generating {format} report #{report_id}")
    return {"report_id": report_id, "format": format, "status": "complete"}


@adapter.task(name="data.cleanup")
def cleanup_old_data(days: int = 30) -> dict:
    """Clean up data older than N days."""
    print(f"Cleaning up data older than {days} days")
    return {"deleted_count": 42}


if __name__ == "__main__":
    print("=== OJS Task Enqueue Examples ===\n")

    # Same .delay() API — no changes needed
    print("1. send_email.delay('user@example.com', 'Welcome', 'Hello!')")
    job = send_email.delay("user@example.com", "Welcome", "Hello!")
    print(f"   Enqueued job: {job.id}\n")

    # Same .apply_async() API — queue and countdown work identically
    print("2. generate_report.apply_async(args=[42], queue='reports', countdown=300)")
    job = generate_report.apply_async(args=[42], queue="reports", countdown=300)
    print(f"   Enqueued job: {job.id}\n")

    # Direct task execution still works
    print("3. cleanup_old_data(90)  # direct call")
    result = cleanup_old_data(90)
    print(f"   Result: {result}\n")

    # Clean up
    adapter.close()
    print("Done! Jobs are now managed by the OJS server via HTTP.")
