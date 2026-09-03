# openjobspec-sqlalchemy

SQLAlchemy integration for [Open Job Spec (OJS)](https://github.com/openjobspec/spec) — enqueue background jobs transactionally alongside your database writes.

## Features

- **`enqueue_after_commit()`** — enqueue jobs only when the SQLAlchemy session commits
- **Outbox pattern** — write job requests to an outbox table atomically, then publish reliably
- **Async support** — works with both sync and async SQLAlchemy sessions
- **SQLAlchemy 2.0** — uses `Mapped`, `mapped_column`, and `DeclarativeBase`

## Installation

```bash
pip install openjobspec-sqlalchemy
```

## Quickstart

### Enqueue After Commit

The simplest approach: register a job to be sent to OJS only when the database transaction commits successfully. If the transaction rolls back, the job is never sent.

```python
from sqlalchemy.orm import Session
from ojs_sqlalchemy import enqueue_after_commit


def create_user(session: Session, email: str) -> None:
    user = User(email=email)
    session.add(user)

    # Job is enqueued ONLY if this transaction commits
    enqueue_after_commit(
        session,
        ojs_url="http://localhost:8080",
        job_type="email.welcome",
        args=[email],
        queue="email",
        meta={"source": "signup"},
    )

    session.commit()  # user is saved AND job is enqueued
```

### Async Session Support

For async SQLAlchemy sessions, use `enqueue_after_commit_async`:

```python
from ojs_sqlalchemy import enqueue_after_commit_async


async def create_user(session: Session, email: str) -> None:
    user = User(email=email)
    session.add(user)

    enqueue_after_commit_async(
        session,
        ojs_url="http://localhost:8080",
        job_type="email.welcome",
        args=[email],
    )

    session.commit()
```

### Outbox Pattern

For reliable delivery even when the OJS server is temporarily unavailable, use the outbox pattern. Job requests are written to a database table in the same transaction, then published by a separate process.

**Step 1: Write to the outbox**

```python
from ojs_sqlalchemy import OJSOutbox

outbox = OJSOutbox()


def create_order(session: Session, order_data: dict) -> None:
    order = Order(**order_data)
    session.add(order)

    # Written atomically with the order
    outbox.add(
        session,
        job_type="order.process",
        args=[order.id],
        queue="orders",
    )

    session.commit()
```

**Step 2: Publish from the outbox**

Run the publisher as a background process or periodic task:

```python
from ojs_sqlalchemy import OutboxPublisher

publisher = OutboxPublisher(
    ojs_url="http://localhost:8080",
    session_factory=SessionLocal,
)

# Publish pending entries (call periodically or in a loop)
published = publisher.publish_pending(batch_size=100)

# Or run continuously
publisher.run_forever()  # polls every 1 second by default
```

**Step 3: Clean up old entries**

```python
# Delete published entries older than 1 hour
deleted = publisher.cleanup_published(older_than_seconds=3600)
```

## Outbox Table

The outbox uses a table named `ojs_outbox`. Create it with Alembic or directly:

```python
from ojs_sqlalchemy.models import Base

# With your engine
Base.metadata.create_all(engine)
```

| Column | Type | Description |
|--------|------|-------------|
| `id` | `VARCHAR(36)` | UUID primary key |
| `job_type` | `VARCHAR(255)` | Job type (e.g., `email.send`) |
| `args_json` | `TEXT` | JSON-serialized arguments |
| `queue` | `VARCHAR(255)` | Target queue |
| `meta_json` | `TEXT` | JSON-serialized metadata |
| `priority` | `INTEGER` | Job priority |
| `status` | `VARCHAR(20)` | `pending`, `published`, or `failed` |
| `created_at` | `DATETIME` | Entry creation time |
| `published_at` | `DATETIME` | When published to OJS |

## API Reference

### `enqueue_after_commit(session, ojs_url, job_type, args, **kwargs)`

Register a job to be enqueued via `ojs.SyncClient` after the session commits.

### `enqueue_after_commit_async(session, ojs_url, job_type, args, **kwargs)`

Async version — schedules an asyncio task using `ojs.Client` after commit.

### `OJSOutbox.add(session, job_type, args, *, queue, meta, priority)`

Add a job entry to the outbox table within the current transaction.

### `OutboxPublisher(ojs_url, session_factory, *, batch_size, poll_interval)`

Publisher that polls the outbox table and delivers jobs to OJS.

### `OJSOutboxEntry`

SQLAlchemy mapped class for the `ojs_outbox` table.

## License

Apache-2.0
