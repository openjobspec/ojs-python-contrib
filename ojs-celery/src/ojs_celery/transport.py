"""Celery transport (broker) that uses OJS as the message broker.

This module implements a Kombu-compatible transport that enqueues and
dequeues jobs through the OJS HTTP API, allowing Celery to use an
OJS server as its broker.

Usage in Celery configuration::

    app = Celery("myapp", broker="ojs://localhost:8080")

Or explicitly::

    app.conf.broker_url = "ojs://localhost:8080"
    app.conf.broker_transport = "ojs_celery.transport:OJSTransport"
"""

from __future__ import annotations

import json
import logging
from queue import Empty
from typing import Any

from kombu.transport import virtual
from kombu.utils.encoding import bytes_to_str

import ojs

logger = logging.getLogger(__name__)


def _parse_ojs_url(url: str) -> str:
    """Convert an ojs:// broker URL to an HTTP URL.

    Examples:
        ojs://localhost:8080       → http://localhost:8080
        ojs+tls://ojs.example.com → https://ojs.example.com
        http://localhost:8080      → http://localhost:8080
    """
    if url.startswith("ojs+tls://"):
        return url.replace("ojs+tls://", "https://", 1)
    if url.startswith("ojs://"):
        return url.replace("ojs://", "http://", 1)
    return url


class Channel(virtual.Channel):
    """Kombu channel that maps Celery operations to OJS API calls.

    - ``basic_publish()`` → enqueues an OJS job
    - ``basic_get()``     → fetches a job via OJS worker/fetch
    - ``basic_ack()``     → acknowledges (completes) an OJS job
    - ``basic_reject()``  → fails/retries an OJS job
    """

    _client: ojs.SyncClient | None = None

    @property
    def client(self) -> ojs.SyncClient:
        """Lazy-initialized OJS SyncClient."""
        if self._client is None:
            url = _parse_ojs_url(
                self.connection.client.hostname or "http://localhost:8080"
            )
            self._client = ojs.SyncClient(url)
        return self._client

    def _put(self, queue: str, message: dict[str, Any], **kwargs: Any) -> None:
        """Enqueue a message as an OJS job (called by basic_publish).

        Maps Celery message fields to OJS job envelope:
        - ``task`` header → OJS job ``type``
        - ``argsrepr`` / body → OJS job ``args``
        - Exchange/routing_key → OJS ``queue``
        - ``priority`` → OJS ``priority``
        - ``eta`` → OJS ``scheduled_at``
        """
        headers = message.get("headers", {})
        properties = message.get("properties", {})

        # Extract Celery task name from headers
        task_name = headers.get("task", "celery.unknown")

        # Extract arguments
        body = message.get("body")
        args: list[Any] = []
        if body:
            try:
                decoded = json.loads(body) if isinstance(body, (str, bytes)) else body
                if isinstance(decoded, (list, tuple)) and len(decoded) >= 1:
                    args = list(decoded[0]) if isinstance(decoded[0], (list, tuple)) else [decoded[0]]
            except (json.JSONDecodeError, TypeError, IndexError):
                args = [body]

        # Build OJS enqueue options
        enqueue_kwargs: dict[str, Any] = {"queue": queue}

        priority = properties.get("priority") or headers.get("priority")
        if priority is not None:
            # Celery uses 0-9 (0=highest); map to OJS integer priority
            enqueue_kwargs["priority"] = _celery_priority_to_ojs(int(priority))

        eta = headers.get("eta")
        if eta:
            enqueue_kwargs["delay_until"] = eta

        # Preserve the full Celery message in meta for round-trip fidelity
        meta: dict[str, Any] = {
            "celery_task_id": headers.get("id"),
            "celery_origin": headers.get("origin"),
            "celery_message": message,
        }
        enqueue_kwargs["meta"] = meta

        # Retry policy from Celery headers
        retries = headers.get("retries")
        max_retries = headers.get("max_retries")
        if max_retries is not None:
            enqueue_kwargs["retry"] = {"max_attempts": int(max_retries) + 1}

        try:
            self.client.enqueue(task_name, args, **enqueue_kwargs)
        except Exception:
            logger.error("Failed to enqueue OJS job for task %s", task_name, exc_info=True)
            raise

    def _get(self, queue: str, timeout: float | None = None) -> dict[str, Any]:
        """Fetch a message from OJS (called by basic_get).

        Fetches the next available job from the specified queue and
        converts it back to a Celery-compatible message dict.

        Raises:
            Empty: If no jobs are available.
        """
        try:
            job = self.client.fetch(queue=queue, timeout=1)
        except Exception:
            raise Empty()

        if job is None:
            raise Empty()

        meta = job.meta or {}

        # If we stored the original Celery message, return it for fidelity
        original_message = meta.get("celery_message")
        if original_message and isinstance(original_message, dict):
            # Update delivery info for this consumer
            original_message.setdefault("properties", {})
            original_message["properties"]["delivery_tag"] = job.id
            return original_message

        # Otherwise, reconstruct a Celery message from OJS job data
        body = json.dumps([job.args or [], {}, {}])
        message = {
            "body": body,
            "content-encoding": "utf-8",
            "content-type": "application/json",
            "headers": {
                "task": job.type,
                "id": meta.get("celery_task_id", job.id),
                "retries": job.attempt - 1 if hasattr(job, "attempt") else 0,
                "argsrepr": repr(job.args),
            },
            "properties": {
                "delivery_tag": job.id,
                "delivery_info": {
                    "exchange": "",
                    "routing_key": queue,
                },
                "correlation_id": meta.get("celery_task_id", job.id),
                "reply_to": "",
            },
        }
        return message

    def basic_ack(self, delivery_tag: str, **kwargs: Any) -> None:
        """Acknowledge (complete) an OJS job."""
        try:
            self.client.complete(delivery_tag)
        except Exception:
            logger.warning(
                "Failed to ack OJS job %s", delivery_tag, exc_info=True
            )
        super().basic_ack(delivery_tag, **kwargs)

    def basic_reject(
        self, delivery_tag: str, requeue: bool = False, **kwargs: Any
    ) -> None:
        """Reject an OJS job (fail or requeue)."""
        try:
            if requeue:
                self.client.release(delivery_tag)
            else:
                self.client.fail(delivery_tag, error="Rejected by Celery consumer")
        except Exception:
            logger.warning(
                "Failed to reject OJS job %s", delivery_tag, exc_info=True
            )
        super().basic_reject(delivery_tag, requeue=requeue, **kwargs)

    def _purge(self, queue: str) -> int:
        """Purge all jobs from a queue. Returns count of purged jobs."""
        try:
            result = self.client.purge_queue(queue)
            return result if isinstance(result, int) else 0
        except Exception:
            logger.warning("Failed to purge OJS queue %s", queue, exc_info=True)
            return 0

    def _size(self, queue: str) -> int:
        """Return the number of pending jobs in a queue."""
        try:
            info = self.client.queue_info(queue)
            return info.pending if hasattr(info, "pending") else 0
        except Exception:
            return 0

    def close(self) -> None:
        """Close the OJS client."""
        if self._client is not None:
            self._client.close()
            self._client = None
        super().close()


class Transport(virtual.Transport):
    """Kombu transport that uses OJS as the message broker.

    Register as a Celery broker:

        app = Celery("myapp", broker="ojs://localhost:8080")

    Or in settings::

        CELERY_BROKER_TRANSPORT = "ojs_celery.transport:Transport"
        CELERY_BROKER_URL = "ojs://localhost:8080"
    """

    Channel = Channel

    driver_type = "ojs"
    driver_name = "ojs"

    # Disable the default Kombu cycle-based polling; we use OJS long-poll.
    polling_interval = 1.0

    def driver_version(self) -> str:
        """Return the OJS SDK version."""
        return getattr(ojs, "__version__", "0.1.0")


def _celery_priority_to_ojs(celery_priority: int) -> int:
    """Map Celery priority (0=highest, 9=lowest) to OJS integer priority.

    OJS uses higher values for higher priority, so we invert:
    Celery 0 → OJS 10, Celery 9 → OJS 1.
    """
    clamped = max(0, min(9, celery_priority))
    return 10 - clamped
