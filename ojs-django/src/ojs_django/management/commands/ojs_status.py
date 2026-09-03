"""Django management command to check OJS server and queue status."""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand

from ojs_django.backend import get_client
from ojs_django.conf import get_ojs_settings

logger = logging.getLogger("ojs_django.status")


class Command(BaseCommand):
    help = "Check OJS server health and display queue statistics."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--queue",
            type=str,
            default=None,
            help="Show details for a specific queue.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            default=False,
            help="Output in JSON format.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        import json

        cfg = get_ojs_settings()
        client = get_client()

        # Health check
        try:
            health = client.health()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Cannot connect to OJS server at {cfg.url}: {exc}"))
            return

        if options["json"]:
            result: dict[str, Any] = {"server": cfg.url, "health": health}
        else:
            status = health.get("status", "unknown")
            color = self.style.SUCCESS if status == "ok" else self.style.ERROR
            self.stdout.write(f"Server: {cfg.url}")
            self.stdout.write(f"Status: {color(status)}")

        # Queue details
        if options["queue"]:
            queue_name = cfg.prefixed_queue(options["queue"])
            try:
                stats = client.queue_stats(queue_name)
                if options["json"]:
                    result["queue"] = {"name": queue_name, "stats": _stats_to_dict(stats)}
                else:
                    self.stdout.write(f"\nQueue: {queue_name}")
                    _print_stats(self, stats)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Failed to get queue stats: {exc}"))
        else:
            # List all queues
            try:
                queues = client.list_queues()
                if options["json"]:
                    result["queues"] = []
                else:
                    self.stdout.write(f"\nQueues ({len(queues)}):")
                    self.stdout.write("-" * 50)

                for q in queues:
                    name = q.name if hasattr(q, "name") else str(q)
                    try:
                        stats = client.queue_stats(name)
                        if options["json"]:
                            result["queues"].append({"name": name, "stats": _stats_to_dict(stats)})
                        else:
                            self.stdout.write(f"\n  {name}:")
                            _print_stats(self, stats, indent=4)
                    except Exception:
                        if options["json"]:
                            result["queues"].append({"name": name, "stats": None})
                        else:
                            self.stdout.write(f"\n  {name}: (stats unavailable)")
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Failed to list queues: {exc}"))

        if options["json"]:
            self.stdout.write(json.dumps(result, indent=2, default=str))


def _stats_to_dict(stats: Any) -> dict[str, Any]:
    """Convert queue stats to a plain dict."""
    if hasattr(stats, "__dict__"):
        return {k: v for k, v in stats.__dict__.items() if not k.startswith("_")}
    return {"raw": str(stats)}


def _print_stats(cmd: BaseCommand, stats: Any, indent: int = 2) -> None:
    """Print queue statistics."""
    prefix = " " * indent
    for attr in ("available", "active", "completed", "retryable", "discarded", "cancelled"):
        value = getattr(stats, attr, None)
        if value is not None:
            cmd.stdout.write(f"{prefix}{attr}: {value}")
