# ojs-agentcore

OJS adapter for AWS Bedrock AgentCore — read-only export of AgentCore sessions
as OJS agent envelopes.

## Overview

This package converts Bedrock AgentCore sessions into OJS-compatible job
envelopes for interoperability, auditing, and transparency log submission.
It is a **read-only** adapter: it queries AgentCore sessions and maps them
to OJS structures without modifying the AgentCore state.

## Installation

```bash
pip install ojs-agentcore
```

## Quick Start

```python
import asyncio
from ojs_agentcore import AgentCoreExporter

async def main():
    exporter = AgentCoreExporter("http://localhost:8080")

    # Export a single session
    envelope = await exporter.export_session("session-123")
    print(envelope)

    # Export all sessions for an agent
    envelopes = await exporter.export_all("agent-456", limit=50)
    print(f"Exported {len(envelopes)} sessions")

asyncio.run(main())
```

## OJS Envelope Format

Each exported session produces an OJS job envelope with:

- `type`: `"agentcore.session"`
- `args`: `[session_id]`
- `ext_agent_v2`: Agent extension fields including source, agent/session IDs,
  turn count, and mapped status

## License

Apache-2.0
