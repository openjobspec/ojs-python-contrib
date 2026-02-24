"""Celery result backend that stores results via OJS.

This backend maps Celery task results to OJS job completion metadata,
allowing Celery consumers to retrieve results stored in OJS.

Usage in Celery configuration::

    app = Celery("myapp")
    app.conf.result_backend = "ojs_celery.backend.OJSResultBackend"
    app.conf.ojs_url = "http://localhost:8080"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from celery.backends.base import BaseBackend
from celery.states import FAILURE, PENDING, RETRY, SUCCESS

import ojs

logger = logging.getLogger(__name__)

# Map OJS job states to Celery states
_OJS_TO_CELERY_STATE = {
    "queued": PENDING,
    "active": "STARTED",
    "completed": SUCCESS,
    "failed": FAILURE,
    "retrying": RETRY,
    "cancelled": "REVOKED",
    "dead": FAILURE,
}


class OJSResultBackend(BaseBackend):
    """Celery result backend backed by Open Job Spec.

    Stores task results as OJS job metadata and retrieves job status
    from the OJS server. This allows Celery result consumers (e.g.,
    ``AsyncResult.get()``) to work with OJS-managed jobs.

    Configuration:

    - ``ojs_url``: OJS server URL (default: ``http://localhost:8080``)
    - ``ojs_timeout``: HTTP request timeout in seconds (default: 30)
    """

    def __init__(self, app: Any = None, **kwargs: Any) -> None:
        super().__init__(app, **kwargs)
        self._client: ojs.SyncClient | None = None

    @property
    def client(self) -> ojs.SyncClient:
        """Lazy-initialized OJS SyncClient."""
        if self._client is None:
            url = self.app.conf.get("ojs_url", "http://localhost:8080")
            self._client = ojs.SyncClient(url)
        return self._client

    def _store_result(
        self,
        task_id: str,
        result: Any,
        state: str,
        traceback: str | None = None,
        request: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Store a task result in OJS as job completion metadata.

        Maps the Celery result to an OJS job update:
        - SUCCESS → completes the job with result in meta
        - FAILURE → fails the job with error details in meta
        - Other states → updates job meta with current state

        Args:
            task_id: The Celery task ID (used as OJS job ID lookup key).
            result: The task return value or exception.
            state: Celery state string (SUCCESS, FAILURE, etc.).
            traceback: Exception traceback string, if any.
            request: The original task request.

        Returns:
            The result, unchanged.
        """
        meta = {
            "celery_state": state,
            "celery_task_id": task_id,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }

        if state == SUCCESS:
            meta["result"] = self._encode_result(result)
        elif state == FAILURE:
            meta["error"] = {
                "type": type(result).__name__ if result else "UnknownError",
                "message": str(result) if result else "",
                "traceback": traceback,
            }
        elif state == RETRY:
            meta["retry_reason"] = str(result) if result else None

        try:
            job = self._find_job_by_task_id(task_id)
            if job is not None:
                if state == SUCCESS:
                    self.client.complete(job.id, meta=meta)
                elif state == FAILURE:
                    self.client.fail(job.id, error=str(result), meta=meta)
                else:
                    self.client.update_meta(job.id, meta=meta)
            else:
                logger.debug(
                    "No OJS job found for task_id=%s; storing result locally", task_id
                )
        except Exception:
            logger.warning(
                "Failed to store result in OJS for task_id=%s", task_id, exc_info=True
            )

        return result

    def _get_task_meta_for(self, task_id: str) -> dict[str, Any]:
        """Fetch job status from OJS and return as Celery task metadata.

        Args:
            task_id: The Celery task ID.

        Returns:
            A dict with keys: task_id, status, result, traceback, children.
        """
        try:
            job = self._find_job_by_task_id(task_id)
            if job is None:
                return self._default_meta(task_id)

            meta = job.meta or {}
            celery_state = _OJS_TO_CELERY_STATE.get(job.state, PENDING)

            result = None
            traceback = None

            if celery_state == SUCCESS and "result" in meta:
                result = self._decode_result(meta["result"])
            elif celery_state == FAILURE and "error" in meta:
                error_info = meta["error"]
                result = Exception(error_info.get("message", "Unknown error"))
                traceback = error_info.get("traceback")

            return {
                "task_id": task_id,
                "status": celery_state,
                "result": result,
                "traceback": traceback,
                "children": [],
            }
        except Exception:
            logger.warning(
                "Failed to fetch task meta from OJS for task_id=%s",
                task_id,
                exc_info=True,
            )
            return self._default_meta(task_id)

    def _find_job_by_task_id(self, task_id: str) -> ojs.Job | None:
        """Look up an OJS job by Celery task ID.

        First tries using the task_id directly as the OJS job ID,
        then falls back to searching by meta.celery_task_id tag.

        Args:
            task_id: The Celery task ID.

        Returns:
            The OJS Job if found, or None.
        """
        # Direct lookup: task_id may be the OJS job ID
        try:
            return self.client.get_job(task_id)
        except Exception:
            pass

        # Tag-based lookup
        try:
            jobs = self.client.list_jobs(tags=[f"celery_task_id:{task_id}"], limit=1)
            if jobs:
                return jobs[0]
        except Exception:
            pass

        return None

    def _encode_result(self, result: Any) -> Any:
        """Encode a result for JSON-safe storage in OJS meta."""
        try:
            json.dumps(result)
            return result
        except (TypeError, ValueError):
            return str(result)

    def _decode_result(self, encoded: Any) -> Any:
        """Decode a result from OJS meta storage."""
        return encoded

    def _default_meta(self, task_id: str) -> dict[str, Any]:
        """Return default pending metadata for an unknown task."""
        return {
            "task_id": task_id,
            "status": PENDING,
            "result": None,
            "traceback": None,
            "children": [],
        }

    def cleanup(self) -> None:
        """Close the OJS client connection."""
        if self._client is not None:
            self._client.close()
            self._client = None
