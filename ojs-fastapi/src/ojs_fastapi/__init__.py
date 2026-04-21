"""FastAPI integration for Open Job Spec (OJS)."""

from ojs_fastapi.cron import CronRegistration, OJSCronBridge
from ojs_fastapi.depends import OJSPlugin, get_ojs_client
from ojs_fastapi.events import EventSubscription, OJSEventManager
from ojs_fastapi.handlers import JobHandler, OJSHandlerRegistry, ojs_handler
from ojs_fastapi.health import HealthResponse, create_health_router
from ojs_fastapi.lifespan import ojs_lifespan
from ojs_fastapi.models import EnqueueRequest, EnqueueResponse, JobResponse
from ojs_fastapi.workflow import WorkflowBuilder, get_ojs_workflow, get_workflow_builder

__all__ = [
    "CronRegistration",
    "EnqueueRequest",
    "EnqueueResponse",
    "EventSubscription",
    "HealthResponse",
    "JobHandler",
    "JobResponse",
    "OJSCronBridge",
    "OJSEventManager",
    "OJSHandlerRegistry",
    "OJSPlugin",
    "WorkflowBuilder",
    "create_health_router",
    "get_ojs_client",
    "get_ojs_workflow",
    "get_workflow_builder",
    "ojs_handler",
    "ojs_lifespan",
]
