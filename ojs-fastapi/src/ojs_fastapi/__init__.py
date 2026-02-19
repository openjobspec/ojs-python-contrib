"""FastAPI integration for Open Job Spec (OJS)."""

from ojs_fastapi.depends import OJSPlugin, get_ojs_client
from ojs_fastapi.handlers import OJSHandlerRegistry, ojs_handler, JobHandler
from ojs_fastapi.lifespan import ojs_lifespan
from ojs_fastapi.models import EnqueueRequest, EnqueueResponse, JobResponse

__all__ = [
    "EnqueueRequest",
    "EnqueueResponse",
    "JobHandler",
    "JobResponse",
    "OJSHandlerRegistry",
    "OJSPlugin",
    "get_ojs_client",
    "ojs_handler",
    "ojs_lifespan",
]
