# OJS Celery Migration Examples

Side-by-side examples showing Celery code and its OJS equivalent.

## Setup

```bash
# Start the OJS server and Redis
docker compose up -d

# Install dependencies
pip install -r requirements.txt
```

## Files

| File | Description |
|------|-------------|
| `before_celery.py` | Original application using Celery tasks |
| `after_ojs.py` | Same application migrated to OJS via the Celery adapter |
| `docker-compose.yml` | Redis + OJS server for running the examples |

## Running

```bash
# View the original Celery code
python before_celery.py

# Run the migrated OJS version (requires OJS server running)
python after_ojs.py
```

## What Changes

1. Replace `from celery import Celery` with `from ojs_celery import OJSAdapter`
2. Replace `app = Celery(...)` with `adapter = OJSAdapter(ojs_url=...)`
3. Replace `@app.task(...)` with `@adapter.task(...)`
4. `.delay()` and `.apply_async()` calls remain identical
