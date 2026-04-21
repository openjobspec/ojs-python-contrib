"""Tests for OJS Django admin views."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import RequestFactory

from ojs_django.admin import OJSAdminSite, OJSAdminView


def _make_staff_request(path: str = "/admin/ojs/") -> MagicMock:
    factory = RequestFactory()
    request = factory.get(path)
    request.user = MagicMock()
    request.user.is_staff = True
    request.user.is_active = True
    request.user.has_perm.return_value = True
    return request


def test_dashboard_healthy() -> None:
    """Dashboard should display health info for healthy server."""
    mock_client = MagicMock()
    mock_client.health.return_value = {"status": "ok"}
    mock_client.list_queues.return_value = []

    request = _make_staff_request()
    with patch("ojs_django.admin.get_client", return_value=mock_client):
        response = OJSAdminView.dashboard(request)

    assert response.status_code == 200


def test_dashboard_unhealthy() -> None:
    """Dashboard should handle connection errors gracefully."""
    request = _make_staff_request()
    with patch("ojs_django.admin.get_client", side_effect=ConnectionError("refused")):
        response = OJSAdminView.dashboard(request)

    assert response.status_code == 200


def test_dead_letter_view() -> None:
    """Dead letter view should display jobs."""
    mock_client = MagicMock()
    mock_client.list_dead_letter_jobs.return_value = {
        "jobs": [{"id": "j1", "type": "test", "queue": "default", "state": "discarded"}],
        "pagination": {},
    }

    request = _make_staff_request("/admin/ojs/dead-letter/")
    with patch("ojs_django.admin.get_client", return_value=mock_client):
        response = OJSAdminView.dead_letter(request)

    assert response.status_code == 200


def test_admin_urls_registered() -> None:
    """Admin URL patterns should be generated."""
    urls = OJSAdminSite.get_urls()
    assert len(urls) == 4
    url_names = [u.name for u in urls]
    assert "ojs_dashboard" in url_names
    assert "ojs_queues" in url_names
    assert "ojs_dead_letter" in url_names


def test_queues_view_fetches_stats_by_name() -> None:
    """Queues view should render and fetch stats using each queue's name."""
    q = MagicMock()
    q.name = "emails"
    mock_client = MagicMock()
    mock_client.list_queues.return_value = [q]
    mock_client.queue_stats.return_value = {"pending": 3}

    request = _make_staff_request("/admin/ojs/queues/")
    with patch("ojs_django.admin.get_client", return_value=mock_client):
        response = OJSAdminView.queues(request)

    assert response.status_code == 200
    mock_client.queue_stats.assert_called_once_with("emails")


def test_queues_view_handles_connection_error() -> None:
    """Queues view should degrade gracefully when the server is unreachable."""
    request = _make_staff_request("/admin/ojs/queues/")
    with patch("ojs_django.admin.get_client", side_effect=ConnectionError("refused")):
        response = OJSAdminView.queues(request)

    assert response.status_code == 200


def test_queue_detail_view() -> None:
    """Queue detail view should render stats for a single queue."""
    mock_client = MagicMock()
    mock_client.queue_stats.return_value = {"pending": 1}

    request = _make_staff_request("/admin/ojs/queues/default/")
    with patch("ojs_django.admin.get_client", return_value=mock_client):
        response = OJSAdminView.queue_detail(request, "default")

    assert response.status_code == 200
    mock_client.queue_stats.assert_called_once_with("default")
