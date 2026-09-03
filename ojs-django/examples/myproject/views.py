"""Example Django view that enqueues a job after the DB transaction commits."""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Ensure job handlers are imported so they are registered
import myproject.jobs  # noqa: F401
from ojs_django import enqueue_after_commit


@csrf_exempt
@require_POST
def enqueue_email(request: HttpRequest) -> JsonResponse:
    """Enqueue an email.send job inside a transaction.

    POST /enqueue/ with JSON body: {"to": "user@example.com", "template": "welcome"}

    The job is only sent to the OJS server after the DB transaction commits.
    """
    body = json.loads(request.body)
    to = body.get("to", "default@example.com")
    template = body.get("template", "welcome")

    # enqueue_after_commit defers the enqueue until the transaction commits.
    # If using ATOMIC_REQUESTS or wrapping in transaction.atomic(), the job
    # will not be sent if the request/transaction fails.
    enqueue_after_commit(
        "email.send",
        [to, template],
        queue="email",
        meta={"source": "web"},
    )

    return JsonResponse({"status": "queued", "to": to, "template": template})
