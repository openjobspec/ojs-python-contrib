"""FastAPI integration for Open Job Spec (OJS)."""

from ojs_fastapi.depends import OJSPlugin, get_ojs_client
from ojs_fastapi.lifespan import ojs_lifespan
from ojs_fastapi.models import EnqueueRequest, EnqueueResponse, JobResponse

__all__ = [
    "EnqueueRequest",
    "EnqueueResponse",
    "JobResponse",
    "OJSPlugin",
    "get_ojs_client",
    "ojs_lifespan",
]
