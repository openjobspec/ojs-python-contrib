"""Django middleware for request-scoped OJS context propagation.

Provides:
- Thread-local OJS client scoped to the request lifecycle.
- Automatic propagation of request context (user, request ID) to jobs.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse

from ojs_django.conf import get_ojs_settings

# Thread-local storage for request context
_local = threading.local()


class OJSMiddleware:
    """Django middleware that sets up request-scoped OJS context.

    Adds the following to each request:
    - ``request.ojs_meta``: A dict of context metadata automatically
      attached to jobs enqueued during the request.
    - ``request.ojs_request_id``: A unique ID for the request.

    Jobs enqueued via ``ojs_django.backend`` during a request will
    automatically include the request context in their metadata.

    Configuration in ``settings.py``::

        MIDDLEWARE = [
            ...
            "ojs_django.middleware.OJSMiddleware",
            ...
        ]
    """

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = self._get_request_id(request)
        meta: dict[str, Any] = {
            "request_id": request_id,
        }

        # Add user info if authenticated
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            meta["user_id"] = str(user.pk)
            username = getattr(user, "username", None)
            if username:
                meta["username"] = username

        request.ojs_meta = meta  # type: ignore[attr-defined]
        request.ojs_request_id = request_id  # type: ignore[attr-defined]

        _local.ojs_meta = meta
        _local.ojs_request_id = request_id

        try:
            response = self.get_response(request)
        finally:
            _local.ojs_meta = None
            _local.ojs_request_id = None

        return response

    @staticmethod
    def _get_request_id(request: HttpRequest) -> str:
        """Extract or generate a request ID."""
        for header in ("X-Request-ID", "X-Correlation-ID"):
            value = request.META.get(f"HTTP_{header.upper().replace('-', '_')}")
            if value:
                return str(value)
        return uuid.uuid4().hex


def get_current_ojs_meta() -> dict[str, Any] | None:
    """Return the OJS metadata for the current request, or None.

    This function is safe to call outside a request context.
    """
    return getattr(_local, "ojs_meta", None)


def get_current_request_id() -> str | None:
    """Return the OJS request ID for the current request, or None."""
    return getattr(_local, "ojs_request_id", None)


def get_ojs_client() -> Any:
    """Return a lazily-initialized, process-wide OJS SyncClient.

    This is a convenience alias that also works outside request context.
    """
    from ojs_django.backend import get_client

    return get_client()
