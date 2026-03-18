"""OpenJobSpec SQLAlchemy integration.

Provides transactional enqueue helpers and an outbox pattern
for reliable OJS job delivery with SQLAlchemy.
"""

from ojs_sqlalchemy.background import BackgroundOutboxPublisher, PublishStats
from ojs_sqlalchemy.enqueue import enqueue_after_commit, enqueue_after_commit_async
from ojs_sqlalchemy.events import JobStateEvent, OJSEventListener
from ojs_sqlalchemy.health import OutboxHealthCheck
from ojs_sqlalchemy.models import OJSOutboxEntry
from ojs_sqlalchemy.outbox import OJSOutbox, OutboxPublisher

__all__ = [
    "BackgroundOutboxPublisher",
    "JobStateEvent",
    "OJSEventListener",
    "OJSOutbox",
    "OJSOutboxEntry",
    "OutboxHealthCheck",
    "OutboxPublisher",
    "PublishStats",
    "enqueue_after_commit",
    "enqueue_after_commit_async",
]
