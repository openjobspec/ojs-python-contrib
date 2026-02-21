"""Pydantic models for OJS FastAPI integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EnqueueRequest(BaseModel):
    """Request model for enqueuing a job via a FastAPI endpoint."""

    type: str = Field(..., description="Dot-namespaced job type (e.g. 'email.send')")
    args: list[Any] = Field(default_factory=list, description="Positional arguments for the job")
    queue: str = Field(default="default", description="Target queue name")
    meta: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    priority: int = Field(default=0, description="Job priority (higher = more urgent)")


class EnqueueResponse(BaseModel):
    """Response model returned after enqueuing a job."""

    job_id: str = Field(..., description="UUIDv7 job identifier")
    type: str = Field(..., description="Job type")
    state: str = Field(..., description="Current job state")
    queue: str = Field(..., description="Queue the job was enqueued to")


class JobResponse(BaseModel):
    """Full job response model."""

    job_id: str = Field(..., description="UUIDv7 job identifier")
    type: str = Field(..., description="Job type")
    state: str = Field(..., description="Current job state")
    queue: str = Field(default="default", description="Queue name")
    args: list[Any] = Field(default_factory=list, description="Job arguments")
    meta: dict[str, Any] = Field(default_factory=dict, description="Job metadata")
    priority: int = Field(default=0, description="Job priority")
    attempt: int = Field(default=0, description="Current attempt number")
    created_at: str | None = Field(default=None, description="ISO 8601 creation timestamp")
    enqueued_at: str | None = Field(default=None, description="ISO 8601 enqueue timestamp")
    started_at: str | None = Field(default=None, description="ISO 8601 start timestamp")
    completed_at: str | None = Field(default=None, description="ISO 8601 completion timestamp")
    result: Any = Field(default=None, description="Job result data")

