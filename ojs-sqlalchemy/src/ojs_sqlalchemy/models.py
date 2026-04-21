"""SQLAlchemy model for the OJS outbox table."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Default declarative base for standalone usage."""


class OJSOutboxEntry(Base):
    """Outbox entry for reliable OJS job delivery.

    Stores pending job enqueue requests in the same database transaction
    as your application data, ensuring at-least-once delivery.

    Attributes:
        id: Unique identifier for the outbox entry.
        job_type: Dot-namespaced job type (e.g., "email.send").
        args_json: JSON-serialized positional arguments.
        queue: Target queue name.
        meta_json: JSON-serialized metadata.
        priority: Job priority (higher = more important).
        status: Entry status: "pending", "published", or "failed".
        created_at: When the entry was created.
        published_at: When the entry was successfully published to OJS.
    """

    __tablename__ = "ojs_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    job_type: Mapped[str] = mapped_column(String(255), nullable=False)
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    queue: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    meta_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    @property
    def args(self) -> list[Any]:
        """Deserialize args from JSON."""
        return json.loads(self.args_json)  # type: ignore[no-any-return]

    @args.setter
    def args(self, value: list[Any]) -> None:
        """Serialize args to JSON."""
        self.args_json = json.dumps(value)

    @property
    def meta(self) -> dict[str, Any]:
        """Deserialize meta from JSON."""
        return json.loads(self.meta_json)  # type: ignore[no-any-return]

    @meta.setter
    def meta(self, value: dict[str, Any]) -> None:
        """Serialize meta to JSON."""
        self.meta_json = json.dumps(value)

    def __repr__(self) -> str:
        return f"OJSOutboxEntry(id={self.id!r}, job_type={self.job_type!r}, status={self.status!r})"
