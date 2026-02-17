"""URL configuration for the OJS example project."""

from django.http import JsonResponse
from django.urls import path

from myproject import views

urlpatterns = [
    path("enqueue/", views.enqueue_email, name="enqueue_email"),
    path("health/", lambda r: JsonResponse({"status": "ok"}), name="health"),
]
