"""Django management command to start an OJS worker.

Usage::

    python manage.py ojs_worker
    python manage.py ojs_worker --queues default,email --concurrency 10
    python manage.py ojs_worker --poll-interval 5.0 --shutdown-timeout 30
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

from django.core.management.base import BaseCommand
from django.utils.module_loading import autodiscover_modules

import ojs

from ojs_django.conf import get_ojs_settings
from ojs_django.decorators import get_registry

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
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=None,
            help="Seconds between poll cycles when idle (overrides OJS_POLL_INTERVAL).",
        )
        parser.add_argument(
            "--shutdown-timeout",
            type=int,
            default=30,
            help="Seconds to wait for active jobs to finish on shutdown (default: 30).",
        )
        parser.add_argument(
            "--autodiscover",
            action="store_true",
            default=True,
            help="Auto-discover jobs.py modules in installed apps (default: True).",
        )
        parser.add_argument(
            "--no-autodiscover",
            action="store_false",
            dest="autodiscover",
            help="Disable auto-discovery of jobs.py modules.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        cfg = get_ojs_settings()

        # Auto-discover job handlers from installed apps
        if options["autodiscover"]:
            autodiscover_modules("jobs")

        queues = cfg.queues
        if options["queues"]:
            queues = [q.strip() for q in options["queues"].split(",")]

        # Apply queue prefix
        queues = [cfg.prefixed_queue(q) for q in queues]

        concurrency = cfg.concurrency
        if options["concurrency"] is not None:
            concurrency = options["concurrency"]

        poll_interval = cfg.poll_interval
        if options["poll_interval"] is not None:
            poll_interval = options["poll_interval"]

        shutdown_timeout = options["shutdown_timeout"]

        registry = get_registry()
        if not registry:
            self.stderr.write(
                self.style.WARNING(
                    "No job handlers registered. "
                    "Ensure modules with @ojs_job decorators are importable, "
                    "or create jobs.py in your Django apps."
                )
            )

        worker = ojs.Worker(
            cfg.url,
            queues=queues,
            concurrency=concurrency,
            poll_interval=poll_interval,
        )

        for job_type, handler in registry.items():
            worker.handler(job_type, handler)
            logger.info("Registered handler: %s -> %s", job_type, handler.__qualname__)

        self.stdout.write(
            self.style.SUCCESS(
                f"Starting OJS worker: queues={queues} concurrency={concurrency} "
                f"poll_interval={poll_interval}s"
            )
        )
        self.stdout.write(
            f"  Handlers: {', '.join(registry.keys()) or '(none)'}"
        )

        # Install graceful shutdown handlers
        loop = asyncio.new_event_loop()
        shutdown_event = asyncio.Event()

        def _signal_handler(sig: int, frame: Any) -> None:
            self.stdout.write(
                self.style.WARNING(f"\nReceived signal {sig}, shutting down gracefully...")
            )
            loop.call_soon_threadsafe(shutdown_event.set)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        async def _run() -> None:
            worker_task = asyncio.create_task(worker.start())

            # Wait for shutdown signal
            await shutdown_event.wait()

            # Graceful shutdown with timeout
            self.stdout.write(
                f"Draining active jobs (timeout={shutdown_timeout}s)..."
            )
            try:
                await asyncio.wait_for(worker.stop(), timeout=shutdown_timeout)
                self.stdout.write(self.style.SUCCESS("Worker stopped gracefully."))
            except asyncio.TimeoutError:
                self.stderr.write(
                    self.style.ERROR(
                        f"Shutdown timed out after {shutdown_timeout}s. "
                        "Some jobs may not have completed."
                    )
                )
                worker_task.cancel()

        try:
            loop.run_until_complete(_run())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Force shutdown."))
            sys.exit(1)
        finally:
            loop.close()
