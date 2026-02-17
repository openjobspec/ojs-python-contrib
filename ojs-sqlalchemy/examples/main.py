"""Example: Transactional job enqueue with SQLAlchemy and OJS.

Demonstrates both the enqueue_after_commit helper and the outbox pattern
for reliable background job delivery.

Prerequisites:
    docker compose up -d   # Start Redis + OJS server
    pip install openjobspec-sqlalchemy
"""

from __future__ import annotations

from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from ojs_sqlalchemy import OJSOutbox, OutboxPublisher, enqueue_after_commit
from ojs_sqlalchemy.models import Base

OJS_URL = "http://localhost:8080"

# ── Database Setup ──────────────────────────────────────────────

engine = create_engine("sqlite:///example.db", echo=True)
SessionLocal = sessionmaker(bind=engine)


# ── Application Models ──────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(255))


# Create all tables (including ojs_outbox)
Base.metadata.create_all(engine)


# ── Example 1: enqueue_after_commit ─────────────────────────────


def create_user_with_welcome_email(email: str, name: str) -> None:
    """Create a user and enqueue a welcome email job on commit."""
    with SessionLocal() as session:
        user = User(email=email, name=name)
        session.add(user)

        enqueue_after_commit(
            session,
            ojs_url=OJS_URL,
            job_type="email.welcome",
            args=[email, name],
            queue="email",
            meta={"source": "signup"},
        )

        session.commit()
        print(f"Created user {email} and enqueued welcome email job")


# ── Example 2: Outbox Pattern ──────────────────────────────────

outbox = OJSOutbox()


def create_user_with_outbox(email: str, name: str) -> None:
    """Create a user and write a job to the outbox atomically."""
    with SessionLocal() as session:
        user = User(email=email, name=name)
        session.add(user)

        outbox.add(
            session,
            job_type="email.welcome",
            args=[email, name],
            queue="email",
            meta={"source": "signup"},
        )

        session.commit()
        print(f"Created user {email} and wrote outbox entry")


def run_outbox_publisher() -> None:
    """Publish pending outbox entries to OJS."""
    publisher = OutboxPublisher(
        ojs_url=OJS_URL,
        session_factory=SessionLocal,
    )
    published = publisher.publish_pending()
    print(f"Published {published} outbox entries")


# ── Main ────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Example 1: enqueue_after_commit ===")
    create_user_with_welcome_email("alice@example.com", "Alice")

    print("\n=== Example 2: Outbox Pattern ===")
    create_user_with_outbox("bob@example.com", "Bob")
    run_outbox_publisher()
