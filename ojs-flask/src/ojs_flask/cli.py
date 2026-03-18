"""Flask CLI commands for Open Job Spec (OJS)."""

from __future__ import annotations

import click
from flask import current_app
from flask.cli import AppGroup

from ojs_flask.helpers import get_client
from ojs_flask.worker import FlaskOJSWorker

ojs_cli = AppGroup("ojs", help="Open Job Spec commands.")


@ojs_cli.command("worker")
@click.option("--queues", default=None, help="Comma-separated queue names.")
@click.option("--concurrency", default=None, type=int, help="Worker concurrency.")
@click.option("--poll-interval", default=None, type=float, help="Poll interval in seconds.")
def worker_cmd(
    queues: str | None,
    concurrency: int | None,
    poll_interval: float | None,
) -> None:
    """Start an OJS worker that processes registered job handlers."""
    app = current_app._get_current_object()  # type: ignore[attr-defined]
    ojs_ext = app.extensions.get("ojs_extension")

    queue_list: list[str] | None = None
    if queues is not None:
        queue_list = [q.strip() for q in queues.split(",") if q.strip()]
    else:
        queue_list = app.config.get("OJS_QUEUES", ["default"])

    if concurrency is None:
        concurrency = app.config.get("OJS_CONCURRENCY", 10)
    if poll_interval is None:
        poll_interval = app.config.get("OJS_POLL_INTERVAL", 2.0)

    click.echo(f"Starting OJS worker (queues={queue_list}, concurrency={concurrency})")

    worker = FlaskOJSWorker(app=app, ojs_ext=ojs_ext)
    worker.start(queues=queue_list, concurrency=concurrency, poll_interval=poll_interval)

    click.echo("OJS worker started. Press Ctrl+C to stop.")
    try:
        import signal

        signal.pause()
    except (KeyboardInterrupt, AttributeError):
        pass
    finally:
        worker.stop()
        click.echo("OJS worker stopped.")


@ojs_cli.command("status")
def status_cmd() -> None:
    """Show OJS server and queue status."""
    try:
        client = get_client()
        health = client.health()
        click.echo(f"Server: healthy ({health})")
    except Exception as exc:
        click.echo(f"Server: unhealthy ({exc})")
        return

    try:
        queues = client.list_queues()
        click.echo(f"Queues ({len(queues)}):")
        for q in queues:
            try:
                stats = client.queue_stats(q)
                click.echo(f"  {q}: {stats}")
            except Exception:
                click.echo(f"  {q}: (unable to fetch stats)")
    except Exception as exc:
        click.echo(f"Unable to list queues: {exc}")


@ojs_cli.command("cron")
@click.argument("job_type")
@click.argument("schedule")
@click.option("--queue", default="default", help="Target queue for the cron job.")
def cron_cmd(job_type: str, schedule: str, queue: str) -> None:
    """Register a cron job with the OJS server.

    JOB_TYPE is the job type identifier (e.g. 'report.daily').
    SCHEDULE is a cron expression (e.g. '*/5 * * * *').
    """
    try:
        client = get_client()
        result = client.enqueue(job_type, [], queue=queue, cron=schedule)
        click.echo(f"Cron job registered: {job_type} ({schedule}) on queue '{queue}'")
        click.echo(f"Job ID: {result}")
    except Exception as exc:
        click.echo(f"Failed to register cron job: {exc}")
        raise SystemExit(1) from exc
