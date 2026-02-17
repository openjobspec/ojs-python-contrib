"""Django integration for Open Job Spec (OJS)."""

from ojs_django.decorators import ojs_job
from ojs_django.enqueue import enqueue, enqueue_after_commit, get_client

__all__ = [
    "enqueue",
    "enqueue_after_commit",
    "get_client",
    "ojs_job",
]

default_app_config = "ojs_django.apps.OjsDjangoConfig"
