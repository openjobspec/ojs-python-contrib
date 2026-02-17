"""Tests for OJS Django middleware."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from ojs_django.middleware import (
    OJSMiddleware,
    get_current_ojs_meta,
    get_current_request_id,
)


def _make_response(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


def test_middleware_sets_request_id() -> None:
    """Middleware should add ojs_request_id to request."""
    factory = RequestFactory()
    request = factory.get("/")
    mw = OJSMiddleware(_make_response)
    mw(request)
    assert hasattr(request, "ojs_request_id")
    assert request.ojs_request_id  # type: ignore[attr-defined]


def test_middleware_uses_x_request_id_header() -> None:
    """Middleware should use X-Request-ID header if present."""
    factory = RequestFactory()
    request = factory.get("/", HTTP_X_REQUEST_ID="abc-123")
    mw = OJSMiddleware(_make_response)
    mw(request)
    assert request.ojs_request_id == "abc-123"  # type: ignore[attr-defined]


def test_middleware_uses_x_correlation_id_header() -> None:
    """Middleware should use X-Correlation-ID header if present."""
    factory = RequestFactory()
    request = factory.get("/", HTTP_X_CORRELATION_ID="corr-456")
    mw = OJSMiddleware(_make_response)
    mw(request)
    assert request.ojs_request_id == "corr-456"  # type: ignore[attr-defined]


def test_middleware_sets_ojs_meta() -> None:
    """Middleware should set ojs_meta on the request."""
    factory = RequestFactory()
    request = factory.get("/")
    mw = OJSMiddleware(_make_response)
    mw(request)
    meta = request.ojs_meta  # type: ignore[attr-defined]
    assert "request_id" in meta


def test_middleware_cleans_up_thread_local() -> None:
    """Thread-local context should be None after request."""
    factory = RequestFactory()
    request = factory.get("/")
    mw = OJSMiddleware(_make_response)
    mw(request)
    assert get_current_ojs_meta() is None
    assert get_current_request_id() is None


def test_middleware_context_during_request() -> None:
    """Thread-local should be set during request processing."""
    captured_meta = {}
    captured_request_id = None

    def _capture_response(request: HttpRequest) -> HttpResponse:
        nonlocal captured_meta, captured_request_id
        captured_meta = get_current_ojs_meta() or {}
        captured_request_id = get_current_request_id()
        return HttpResponse("ok")

    factory = RequestFactory()
    request = factory.get("/", HTTP_X_REQUEST_ID="during-test")
    mw = OJSMiddleware(_capture_response)
    mw(request)

    assert captured_meta.get("request_id") == "during-test"
    assert captured_request_id == "during-test"


def test_get_current_outside_request() -> None:
    """Helpers should return None outside request context."""
    assert get_current_ojs_meta() is None
    assert get_current_request_id() is None
