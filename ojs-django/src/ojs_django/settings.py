"""Read OJS configuration from Django settings with sensible defaults."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class OJSSettings:
    """Validated OJS settings from Django configuration."""

    url: str
    queues: list[str]
    concurrency: int
    poll_interval: float


def get_ojs_settings() -> OJSSettings:
    """Build OJS settings from Django's ``settings`` module.

    Reads the following Django settings (all optional):

    - ``OJS_URL`` – OJS server base URL (default: ``"http://localhost:8080"``)
    - ``OJS_QUEUES`` – list of queue names to consume (default: ``["default"]``)
    - ``OJS_CONCURRENCY`` – max concurrent job executions (default: ``10``)
    - ``OJS_POLL_INTERVAL`` – seconds between poll requests (default: ``2.0``)
    """
    return OJSSettings(
        url=getattr(settings, "OJS_URL", "http://localhost:8080"),
        queues=getattr(settings, "OJS_QUEUES", ["default"]),
        concurrency=getattr(settings, "OJS_CONCURRENCY", 10),
        poll_interval=getattr(settings, "OJS_POLL_INTERVAL", 2.0),
    )
