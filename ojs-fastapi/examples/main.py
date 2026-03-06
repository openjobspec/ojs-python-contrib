"""Example FastAPI application with OJS integration.

Run with:
    uvicorn main:app --reload

Requires a running OJS server (see docker-compose.yml).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import ojs
from fastapi import Depends, FastAPI

from ojs_fastapi import EnqueueRequest, EnqueueResponse, OJSPlugin, get_ojs_client, ojs_lifespan
from ojs_fastapi.models import JobResponse

# ---------------------------------------------------------------------------
# OJS plugin configuration
# ---------------------------------------------------------------------------

plugin = OJSPlugin(
    url="http://localhost:8080",
    queues=["default", "emails", "reports"],
    concurrency=5,
)

# Register a worker handler on the plugin's worker
worker = ojs.Worker(
    plugin.url,
    queues=plugin.queues,
    concurrency=plugin.concurrency,
)
plugin._worker = worker  # noqa: SLF001


@worker.register("email.send")
async def handle_email_send(ctx: ojs.JobContext) -> dict[str, Any]:
    """Process an email.send job."""
    to = ctx.args[0] if ctx.args else "unknown"
    print(f"Sending email to {to} (job_id={ctx.job_id})")  # noqa: T201
    return {"sent_to": to, "status": "delivered"}


@worker.register("report.generate")
async def handle_report(ctx: ojs.JobContext) -> dict[str, Any]:
    """Generate a report."""
    report_id = ctx.args[0] if ctx.args else "unknown"
    print(f"Generating report {report_id} (job_id={ctx.job_id})")  # noqa: T201
    return {"report_id": report_id, "pages": 12}


# ---------------------------------------------------------------------------
# FastAPI app with OJS lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    async with ojs_lifespan(app, plugin=plugin) as state:
        yield state


app = FastAPI(
    title="OJS FastAPI Example",
    description="Demonstrates OJS integration with FastAPI",
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/jobs", response_model=EnqueueResponse)
async def enqueue_job(
    body: EnqueueRequest,
    client: ojs.Client = Depends(get_ojs_client),
) -> EnqueueResponse:
    """Enqueue a new background job."""
    job = await client.enqueue(
        body.type,
        body.args,
        queue=body.queue,
        meta=body.meta,
        priority=body.priority,
    )
    return EnqueueResponse(
        job_id=job.id,
        type=job.type,
        state=str(job.state),
        queue=job.queue,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    client: ojs.Client = Depends(get_ojs_client),
) -> JobResponse:
    """Retrieve a job by its ID."""
    job = await client.get_job(job_id)
    return JobResponse(
        job_id=job.id,
        type=job.type,
        state=str(job.state),
        queue=job.queue,
        args=job.args,
        meta=job.meta,
        priority=job.priority,
        attempt=job.attempt,
        created_at=job.created_at.isoformat() if job.created_at else None,
        enqueued_at=job.enqueued_at.isoformat() if job.enqueued_at else None,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result=job.result,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


