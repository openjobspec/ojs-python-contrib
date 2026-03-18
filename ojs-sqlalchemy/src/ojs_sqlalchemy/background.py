"""Background outbox publisher with threading support.

Runs the OutboxPublisher in a daemon thread for automatic background flushing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .outbox import OutboxPublisher

logger = logging.getLogger(__name__)


class BackgroundOutboxPublisher:
    """Runs OutboxPublisher in a background daemon thread.

    Usage::
        publisher = BackgroundOutboxPublisher(
            ojs_url="http://localhost:8080",
            session_factory=SessionLocal,
            flush_interval=2.0,
        )
        publisher.start()

        # ... app runs ...

        publisher.stop()
    """

    def __init__(
        self,
        ojs_url: str,
        session_factory: Any,
        *,
        batch_size: int = 100,
        flush_interval: float = 2.0,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ) -> None:
        self._publisher = OutboxPublisher(
            ojs_url=ojs_url,
            session_factory=session_factory,
            batch_size=batch_size,
            poll_interval=flush_interval,
        )
        self._flush_interval = flush_interval
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._stats = PublishStats()

    @property
    def is_running(self) -> bool:
        """Whether the background publisher thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def stats(self) -> PublishStats:
        """Return the current publish statistics."""
        return self._stats

    def start(self) -> None:
        """Start the background publisher thread."""
        if self.is_running:
            raise RuntimeError("Background publisher is already running.")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ojs-outbox-publisher",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "Background outbox publisher started (interval=%.1fs)", self._flush_interval
        )

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the background publisher."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("Background outbox publisher stopped")

    def flush_now(self) -> int:
        """Trigger an immediate flush cycle (synchronous)."""
        return self._publisher.publish_pending()

    def _run_loop(self) -> None:
        """Main loop executed by the background thread."""
        consecutive_errors = 0
        while not self._stop_event.is_set():
            try:
                count = self._publisher.publish_pending()
                self._stats.total_published += count
                self._stats.cycles += 1
                if count > 0:
                    self._stats.last_publish_count = count
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                self._stats.total_errors += 1
                logger.exception(
                    "Background publisher error (attempt %d)", consecutive_errors
                )
                if consecutive_errors >= self._max_retries:
                    delay = min(self._retry_delay * consecutive_errors, 60.0)
                    self._stop_event.wait(delay)
                    continue

            self._stop_event.wait(self._flush_interval)


class PublishStats:
    """Statistics for the background publisher."""

    def __init__(self) -> None:
        self.total_published: int = 0
        self.total_errors: int = 0
        self.cycles: int = 0
        self.last_publish_count: int = 0

    def to_dict(self) -> dict[str, int]:
        """Return stats as a plain dictionary."""
        return {
            "total_published": self.total_published,
            "total_errors": self.total_errors,
            "cycles": self.cycles,
            "last_publish_count": self.last_publish_count,
        }
