"""Migration helpers for moving from Celery to OJS.

These utilities require Celery to be installed. They are designed to help
plan and execute a migration from Celery to OJS by scanning existing Celery
apps and wrapping Celery tasks for OJS submission.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ojs_celery.adapter import OJSAdapter, OJSTask

if TYPE_CHECKING:
    import celery


def migrate_task(
    celery_task: Any,
    adapter: OJSAdapter | None = None,
    ojs_url: str = "http://localhost:8080",
) -> OJSTask:
    """Wrap an existing Celery task for OJS submission.

    Takes a registered Celery task object and returns an :class:`OJSTask`
    that enqueues jobs via OJS while preserving the original function.

    Args:
        celery_task: A Celery task instance (e.g. ``app.tasks["email.send"]``).
        adapter: Optional :class:`OJSAdapter` to use. If not provided, one is
            created using *ojs_url*.
        ojs_url: OJS server URL (used only when *adapter* is not provided).

    Returns:
        An :class:`OJSTask` with ``.delay()`` and ``.apply_async()`` methods.
    """
    if adapter is None:
        adapter = OJSAdapter(ojs_url=ojs_url)

    task_name: str = celery_task.name
    task_fn = celery_task.run if hasattr(celery_task, "run") else celery_task

    return OJSTask(name=task_name, fn=task_fn, _adapter=adapter)


def scan_celery_tasks(app: celery.Celery) -> list[dict[str, Any]]:
    """Scan a Celery app and return a migration report.

    Inspects all tasks registered with the given Celery app and produces
    structured data describing each task's configuration — useful for
    planning a migration to OJS.

    Args:
        app: A Celery application instance.

    Returns:
        A list of dicts, each containing:

        - ``name``: Task name (str)
        - ``queue``: Bound queue or ``"default"`` (str)
        - ``max_retries``: Max retry count or ``None`` (int | None)
        - ``rate_limit``: Rate limit string or ``None`` (str | None)
        - ``time_limit``: Soft time limit in seconds or ``None`` (float | None)
        - ``acks_late``: Whether the task acks late (bool)
        - ``ojs_equivalent``: Suggested OJS configuration mapping (dict)
    """
    report: list[dict[str, Any]] = []

    for task_name, task_obj in sorted(app.tasks.items()):
        # Skip built-in Celery tasks
        if task_name.startswith("celery."):
            continue

        max_retries = getattr(task_obj, "max_retries", None)
        rate_limit = getattr(task_obj, "rate_limit", None)
        time_limit = getattr(task_obj, "soft_time_limit", None)
        acks_late = getattr(task_obj, "acks_late", False)

        # Determine queue from routing or task binding
        queue = "default"
        if hasattr(task_obj, "queue") and task_obj.queue:
            queue = task_obj.queue

        # Build OJS equivalent configuration
        ojs_config: dict[str, Any] = {
            "job_type": task_name,
            "queue": queue,
        }
        if max_retries is not None:
            ojs_config["retry"] = {"max_attempts": max_retries + 1}
        if time_limit is not None:
            ojs_config["timeout_ms"] = int(time_limit * 1000)

        report.append(
            {
                "name": task_name,
                "queue": queue,
                "max_retries": max_retries,
                "rate_limit": rate_limit,
                "time_limit": time_limit,
                "acks_late": acks_late,
                "ojs_equivalent": ojs_config,
            }
        )

    return report
