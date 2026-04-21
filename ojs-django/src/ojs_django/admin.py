"""Django admin integration for OJS.

Provides read-only admin views for browsing jobs, queues, and
dead-letter jobs. Data is fetched from the OJS server (not from
Django models).
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import path

from ojs_django.backend import get_client
from ojs_django.conf import get_ojs_settings

logger = logging.getLogger("ojs_django.admin")


def _base_context(request: HttpRequest, title: str, **extra: Any) -> dict[str, Any]:
    """Build the shared admin view context (title + staff-permission flag)."""
    return {
        "title": title,
        "has_permission": request.user.is_staff,
        **extra,
    }


def _with_admin_context(context: dict[str, Any], request: HttpRequest) -> dict[str, Any]:
    """Merge Django's admin ``each_context``, degrading outside admin URL setup."""
    with contextlib.suppress(Exception):
        # Gracefully degrade outside full Django URL setup.
        context.update(admin.site.each_context(request))
    return context


class OJSAdminSite:
    """Mixin-like class that registers OJS admin views."""

    @staticmethod
    def get_urls() -> list[Any]:
        return [
            path("ojs/", OJSAdminView.dashboard, name="ojs_dashboard"),
            path("ojs/queues/", OJSAdminView.queues, name="ojs_queues"),
            path(
                "ojs/queues/<str:queue_name>/",
                OJSAdminView.queue_detail,
                name="ojs_queue_detail",
            ),
            path("ojs/dead-letter/", OJSAdminView.dead_letter, name="ojs_dead_letter"),
        ]


class OJSAdminView:
    """Admin views for OJS resources."""

    @staticmethod
    def dashboard(request: HttpRequest) -> HttpResponse:
        """OJS dashboard showing server health and queue overview."""
        context = _base_context(request, "Open Job Spec")

        try:
            client = get_client()
            cfg = get_ojs_settings()
            context["ojs_url"] = cfg.url

            health = client.health()
            context["health"] = health
            context["healthy"] = health.get("status") == "ok"

            queues = client.list_queues()
            context["queues"] = queues
        except Exception:
            logger.exception("Failed to connect to OJS server")
            context["healthy"] = False
            context["error"] = "Could not connect to OJS server"
            context["queues"] = []

        return TemplateResponse(
            request,
            "ojs_django/admin/dashboard.html",
            _with_admin_context(context, request),
        )

    @staticmethod
    def queues(request: HttpRequest) -> HttpResponse:
        """List all queues with statistics."""
        context = _base_context(request, "OJS Queues")

        try:
            client = get_client()
            queues = client.list_queues()
            queue_details = []
            for q in queues:
                try:
                    name = q.name if hasattr(q, "name") else str(q)
                    stats = client.queue_stats(name)
                    queue_details.append({"name": name, "stats": stats})
                except Exception:
                    queue_details.append({"name": name, "stats": None})
            context["queues"] = queue_details
        except Exception:
            logger.exception("Failed to fetch queues")
            context["error"] = "Could not connect to OJS server"
            context["queues"] = []

        return TemplateResponse(
            request,
            "ojs_django/admin/queues.html",
            _with_admin_context(context, request),
        )

    @staticmethod
    def queue_detail(request: HttpRequest, queue_name: str) -> HttpResponse:
        """Show details for a specific queue."""
        context = _base_context(request, f"Queue: {queue_name}", queue_name=queue_name)

        try:
            client = get_client()
            stats = client.queue_stats(queue_name)
            context["stats"] = stats
        except Exception:
            logger.exception("Failed to fetch queue detail for %s", queue_name)
            context["error"] = f"Could not fetch queue: {queue_name}"

        return TemplateResponse(
            request,
            "ojs_django/admin/queue_detail.html",
            _with_admin_context(context, request),
        )

    @staticmethod
    def dead_letter(request: HttpRequest) -> HttpResponse:
        """List dead-letter jobs."""
        context = _base_context(request, "OJS Dead Letter Jobs")

        page = int(request.GET.get("page", 1))
        limit = 50
        offset = (page - 1) * limit

        try:
            client = get_client()
            result = client.list_dead_letter_jobs(limit=limit, offset=offset)
            context["jobs"] = result.get("jobs", [])
            context["pagination"] = result.get("pagination", {})
            context["page"] = page
        except Exception:
            logger.exception("Failed to fetch dead-letter jobs")
            context["error"] = "Could not connect to OJS server"
            context["jobs"] = []

        return TemplateResponse(
            request,
            "ojs_django/admin/dead_letter.html",
            _with_admin_context(context, request),
        )


def register_admin_urls() -> None:
    """Register OJS admin URL patterns with the default admin site."""
    ojs_urls = OJSAdminSite.get_urls()
    original_get_urls = admin.site.get_urls

    def patched_get_urls() -> list[Any]:
        return ojs_urls + original_get_urls()

    admin.site.get_urls = patched_get_urls  # type: ignore[method-assign]
