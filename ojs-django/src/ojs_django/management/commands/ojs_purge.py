"""Django management command to purge the OJS dead letter queue."""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand

from ojs_django.backend import get_client
from ojs_django.conf import get_ojs_settings

logger = logging.getLogger("ojs_django.purge")


class Command(BaseCommand):
    help = "Purge dead letter jobs from the OJS server."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--queue",
            type=str,
            default=None,
            help="Only purge dead letter jobs from this queue.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of dead letter jobs to delete per batch (default: 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be deleted without actually deleting.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        cfg = get_ojs_settings()
        client = get_client()
        queue = options["queue"]
        if queue:
            queue = cfg.prefixed_queue(queue)
        limit = options["limit"]
        dry_run = options["dry_run"]

        try:
            result = client.list_dead_letter_jobs(queue=queue, limit=limit)
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Cannot connect to OJS server at {cfg.url}: {exc}"))
            return

        jobs = result.get("jobs", [])

        if not jobs:
            self.stdout.write(self.style.SUCCESS("No dead letter jobs found."))
            return

        self.stdout.write(f"Found {len(jobs)} dead letter job(s).")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no jobs will be deleted."))
            for job in jobs:
                job_id = job.get("id", job) if isinstance(job, dict) else str(job)
                job_type = job.get("type", "?") if isinstance(job, dict) else "?"
                self.stdout.write(f"  Would delete: {job_id} ({job_type})")
            return

        deleted = 0
        errors = 0
        for job in jobs:
            job_id = job.get("id", str(job)) if isinstance(job, dict) else str(job)
            try:
                client.delete_dead_letter_job(job_id)
                deleted += 1
            except Exception as exc:
                errors += 1
                logger.warning("Failed to delete dead letter job %s: %s", job_id, exc)

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} dead letter job(s)."))
        if errors:
            self.stdout.write(
                self.style.WARNING(f"Failed to delete {errors} job(s). Check logs for details.")
            )
