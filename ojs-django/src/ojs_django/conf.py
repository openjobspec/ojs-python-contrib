"""Read OJS configuration from Django settings.

Supports both the new dict-based format::

    OJS = {
        "URL": "http://localhost:8080",
        "DEFAULT_QUEUE": "default",
        "QUEUE_PREFIX": "",
        "DEFAULT_RETRY": {"max_attempts": 5, "backoff": "exponential"},
        "WORKER": {"concurrency": 10, "queues": ["default", "emails"]},
    }

and the legacy flat format for backward compatibility::

    OJS_URL = "http://localhost:8080"
    OJS_QUEUES = ["default"]
    OJS_CONCURRENCY = 10
    OJS_POLL_INTERVAL = 2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

# Defaults
_DEFAULT_URL = "http://localhost:8080"
_DEFAULT_QUEUE = "default"
_DEFAULT_CONCURRENCY = 10
_DEFAULT_POLL_INTERVAL = 2.0
_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_BACKOFF = "exponential"


@dataclass(frozen=True)
class RetryDefaults:
    """Default retry configuration applied to all jobs unless overridden."""

    max_attempts: int = _DEFAULT_MAX_ATTEMPTS
    backoff: str = _DEFAULT_BACKOFF


@dataclass(frozen=True)
class WorkerSettings:
    """Worker-specific settings."""

    concurrency: int = _DEFAULT_CONCURRENCY
    queues: list[str] = field(default_factory=lambda: [_DEFAULT_QUEUE])
    poll_interval: float = _DEFAULT_POLL_INTERVAL


@dataclass(frozen=True)
class OJSSettings:
    """Validated OJS settings from Django configuration."""

    url: str = _DEFAULT_URL
    default_queue: str = _DEFAULT_QUEUE
    queue_prefix: str = ""
    default_retry: RetryDefaults = field(default_factory=RetryDefaults)
    worker: WorkerSettings = field(default_factory=WorkerSettings)

    # Backward-compatible accessors
    @property
    def queues(self) -> list[str]:
        return self.worker.queues

    @property
    def concurrency(self) -> int:
        return self.worker.concurrency

    @property
    def poll_interval(self) -> float:
        return self.worker.poll_interval

    def prefixed_queue(self, queue: str) -> str:
        """Return queue name with the configured prefix."""
        if self.queue_prefix:
            return f"{self.queue_prefix}{queue}"
        return queue


# Cached singleton
_cached: OJSSettings | None = None


def get_ojs_settings() -> OJSSettings:
    """Build OJS settings from Django's ``settings`` module.

    Reads from the ``OJS`` dict if present, otherwise falls back to
    the legacy flat settings (``OJS_URL``, ``OJS_QUEUES``, etc.).
    """
    global _cached  # noqa: PLW0603
    if _cached is not None:
        return _cached

    ojs_dict: dict[str, Any] | None = getattr(settings, "OJS", None)

    if ojs_dict is not None:
        _cached = _from_dict(ojs_dict)
    else:
        _cached = _from_flat()

    return _cached


def _from_dict(d: dict[str, Any]) -> OJSSettings:
    """Parse the new dict-based ``OJS = {...}`` format."""
    retry_data = d.get("DEFAULT_RETRY", {})
    retry = RetryDefaults(
        max_attempts=retry_data.get("max_attempts", _DEFAULT_MAX_ATTEMPTS),
        backoff=retry_data.get("backoff", _DEFAULT_BACKOFF),
    )

    worker_data = d.get("WORKER", {})
    default_queue = d.get("DEFAULT_QUEUE", _DEFAULT_QUEUE)
    worker = WorkerSettings(
        concurrency=worker_data.get("concurrency", _DEFAULT_CONCURRENCY),
        queues=worker_data.get("queues", [default_queue]),
        poll_interval=worker_data.get("poll_interval", _DEFAULT_POLL_INTERVAL),
    )

    return OJSSettings(
        url=d.get("URL", _DEFAULT_URL),
        default_queue=default_queue,
        queue_prefix=d.get("QUEUE_PREFIX", ""),
        default_retry=retry,
        worker=worker,
    )


def _from_flat() -> OJSSettings:
    """Parse the legacy flat ``OJS_*`` settings format."""
    queues = getattr(settings, "OJS_QUEUES", [_DEFAULT_QUEUE])
    concurrency = getattr(settings, "OJS_CONCURRENCY", _DEFAULT_CONCURRENCY)
    poll_interval = getattr(settings, "OJS_POLL_INTERVAL", _DEFAULT_POLL_INTERVAL)

    return OJSSettings(
        url=getattr(settings, "OJS_URL", _DEFAULT_URL),
        default_queue=_DEFAULT_QUEUE,
        queue_prefix="",
        default_retry=RetryDefaults(),
        worker=WorkerSettings(
            concurrency=concurrency,
            queues=queues,
            poll_interval=poll_interval,
        ),
    )


def reset_settings() -> None:
    """Clear the cached settings. Useful for testing."""
    global _cached  # noqa: PLW0603
    _cached = None
