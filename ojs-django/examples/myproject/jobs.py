"""Example OJS job handlers using the @ojs_job decorator."""

from __future__ import annotations

import logging

import ojs

from ojs_django import ojs_job

logger = logging.getLogger(__name__)


@ojs_job("email.send")
async def handle_email_send(ctx: ojs.JobContext) -> dict[str, object]:
    """Send a welcome email to the given address."""
    to = ctx.args[0]
    template = ctx.args[1] if len(ctx.args) > 1 else "welcome"
    logger.info("Sending %s email to %s (attempt %d)", template, to, ctx.attempt)
    # In a real app: await send_email(to, template)
    return {"sent_to": to, "template": template}


@ojs_job("report.generate")
async def handle_report(ctx: ojs.JobContext) -> dict[str, object]:
    """Generate a report for the given parameters."""
    report_type = ctx.args[0]
    logger.info("Generating %s report", report_type)
    # In a real app: generate and store the report
    return {"report_type": report_type, "status": "generated"}
