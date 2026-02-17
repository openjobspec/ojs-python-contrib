"""Django integration for Open Job Spec (OJS)."""

from ojs_django.backend import (
    enqueue,
    enqueue_after_commit,
    enqueue_at,
    enqueue_batch,
    get_client,
)
from ojs_django.conf import get_ojs_settings
from ojs_django.decorators import OJSJobWrapper, ojs_job

__all__ = [
    "OJSJobWrapper",
    "enqueue",
    "enqueue_after_commit",
    "enqueue_at",
    "enqueue_batch",
    "get_client",
    "get_ojs_settings",
    "ojs_job",
]

default_app_config = "ojs_django.apps.OjsDjangoConfig"
