"""Cron job registration helpers for FastAPI + OJS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CronRegistration:
    """A cron job registration entry."""

    job_type: str
    schedule: str
    args: list[Any] = field(default_factory=list)
    queue: str = "default"
    meta: dict[str, Any] = field(default_factory=dict)


class OJSCronBridge:
    """Manages cron job registrations that are synced to OJS on startup.

    Usage::

        cron = OJSCronBridge()

        cron.register("reports.daily", "0 6 * * *", queue="reports")
        cron.register("cleanup.stale", "0 */4 * * *")

        # In lifespan:
        await cron.sync(client)
    """

    def __init__(self) -> None:
        self._registrations: list[CronRegistration] = []

    def register(
        self,
        job_type: str,
        schedule: str,
        *,
        args: list[Any] | None = None,
        queue: str = "default",
        meta: dict[str, Any] | None = None,
    ) -> CronRegistration:
        """Register a cron job to be synced on startup."""
        reg = CronRegistration(
            job_type=job_type,
            schedule=schedule,
            args=args or [],
            queue=queue,
            meta=meta or {},
        )
        self._registrations.append(reg)
        return reg

    @property
    def registrations(self) -> list[CronRegistration]:
        """Return a copy of all registered cron jobs."""
        return list(self._registrations)

    async def sync(self, client: Any) -> list[Any]:
        """Sync all registered cron jobs with the OJS server.

        Args:
            client: An ojs.Client instance.

        Returns:
            List of registered cron job results.
        """
        results = []
        for reg in self._registrations:
            try:
                result = await client.register_cron_job(
                    name=reg.job_type,
                    cron=reg.schedule,
                    job_type=reg.job_type,
                    args=reg.args,
                    queue=reg.queue,
                    meta=reg.meta,
                )
                results.append(result)
                logger.info("Registered cron: %s [%s]", reg.job_type, reg.schedule)
            except Exception:
                logger.exception("Failed to register cron: %s", reg.job_type)
        return results
