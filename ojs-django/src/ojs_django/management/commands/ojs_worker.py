"""Django management command to start an OJS worker."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from django.core.management.base import BaseCommand

import ojs

from ojs_django.decorators import get_registry
from ojs_django.settings import get_ojs_settings

logger = logging.getLogger("ojs_django.worker")


class Command(BaseCommand):
    help = "Start an OJS background job worker."  # noqa: A003

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--queues",
            type=str,
            default=None,
            help="Comma-separated list of queues to consume (overrides OJS_QUEUES setting).",
        )
        parser.add_argument(
            "--concurrency",
            type=int,
            default=None,
            help="Maximum concurrent job executions (overrides OJS_CONCURRENCY setting).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        cfg = get_ojs_settings()

        queues = cfg.queues
        if options["queues"]:
            queues = [q.strip() for q in options["queues"].split(",")]

        concurrency = cfg.concurrency
        if options["concurrency"] is not None:
            concurrency = options["concurrency"]

        registry = get_registry()
        if not registry:
            self.stderr.write(
                self.style.WARNING(
                    "No job handlers registered. "
                    "Import modules that use @ojs_job before starting the worker."
                )
            )

        worker = ojs.Worker(
            cfg.url,
            queues=queues,
            concurrency=concurrency,
            poll_interval=cfg.poll_interval,
        )

        for job_type, handler in registry.items():
            worker.handler(job_type, handler)
            logger.info("Registered handler: %s -> %s", job_type, handler.__qualname__)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting OJS worker: queues={queues} concurrency={concurrency}"
            )
        )

        asyncio.run(worker.start())
