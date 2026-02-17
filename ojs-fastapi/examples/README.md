# OJS FastAPI Example

A complete FastAPI application demonstrating OJS integration with dependency injection,
lifespan-managed workers, and job endpoints.

## Quick Start

1. **Start the OJS server and Redis:**

   ```bash
   docker compose up -d
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the FastAPI application:**

   ```bash
   uvicorn main:app --reload
   ```

4. **Enqueue a job:**

   ```bash
   curl -X POST http://localhost:8000/jobs \
     -H "Content-Type: application/json" \
     -d '{"type": "email.send", "args": ["user@example.com"], "queue": "emails"}'
   ```

5. **Check job status:**

   ```bash
   curl http://localhost:8000/jobs/<job_id>
   ```

## Architecture

- **Lifespan** — The OJS client and worker are started on app startup and shut down
  gracefully when the app stops.
- **Dependency Injection** — `get_ojs_client` provides the shared `ojs.Client` to any
  endpoint via `Depends()`.
- **Worker Handlers** — Job handlers are registered on the worker and run in-process
  alongside the FastAPI server.
