"""OJS adapter for AWS Bedrock AgentCore (read-only export).

Converts Bedrock AgentCore sessions into OJS agent envelopes for
interoperability, auditing, and transparency log submission.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AgentCoreSession:
    """Represents a single AgentCore session exported as an OJS envelope."""

    session_id: str
    agent_id: str
    created_at: datetime
    turns: list[dict[str, Any]] = field(default_factory=list)
    status: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentCoreExporter:
    """Exports Bedrock AgentCore sessions as OJS agent envelopes.

    This is a read-only adapter: it queries AgentCore sessions and
    converts them to OJS-compatible job envelopes. It does not modify
    the AgentCore state.

    Example::

        exporter = AgentCoreExporter("http://localhost:8080")
        envelope = await exporter.export_session("session-123")
    """

    def __init__(self, ojs_url: str = "http://localhost:8080") -> None:
        self._ojs_url = ojs_url.rstrip("/")

    async def export_session(self, session_id: str) -> dict[str, Any]:
        """Export a single AgentCore session as an OJS envelope.

        Args:
            session_id: The AgentCore session identifier.

        Returns:
            An OJS job envelope dict with ext_agent_v2 extension fields.
        """
        session = await self._fetch_session(session_id)
        return self._to_ojs_envelope(session)

    async def export_all(
        self, agent_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Export all sessions for an agent as OJS envelopes.

        Args:
            agent_id: The AgentCore agent identifier.
            limit: Maximum number of sessions to export.

        Returns:
            A list of OJS job envelope dicts.
        """
        sessions = await self._list_sessions(agent_id, limit)
        return [self._to_ojs_envelope(s) for s in sessions]

    def _to_ojs_envelope(self, session: AgentCoreSession) -> dict[str, Any]:
        """Convert an AgentCore session to an OJS job envelope."""
        return {
            "type": "agentcore.session",
            "args": [session.session_id],
            "options": {
                "queue": "agentcore-export",
            },
            "ext_agent_v2": {
                "state": _map_status(session.status),
                "source": "aws-bedrock-agentcore",
                "agent_id": session.agent_id,
                "session_id": session.session_id,
                "turn_count": len(session.turns),
                "created_at": session.created_at.isoformat(),
            },
            "metadata": session.metadata,
        }

    async def _fetch_session(self, session_id: str) -> AgentCoreSession:
        """Fetch a session from AgentCore. Placeholder for real API call."""
        # In production this would call the AgentCore API.
        # For now, return a stub to validate the interface.
        return AgentCoreSession(
            session_id=session_id,
            agent_id="placeholder",
            created_at=datetime.now(timezone.utc),
            turns=[],
            status="completed",
        )

    async def _list_sessions(
        self, agent_id: str, limit: int
    ) -> list[AgentCoreSession]:
        """List sessions for an agent. Placeholder for real API call."""
        return [
            AgentCoreSession(
                session_id=f"{agent_id}-session-0",
                agent_id=agent_id,
                created_at=datetime.now(timezone.utc),
                turns=[],
                status="completed",
            )
        ]


def _map_status(agentcore_status: str) -> str:
    """Map AgentCore status to OJS agent state."""
    mapping = {
        "completed": "completed",
        "in_progress": "running",
        "failed": "failed",
        "cancelled": "cancelled",
        "unknown": "pending",
    }
    return mapping.get(agentcore_status, "pending")
