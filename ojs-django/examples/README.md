# OJS Django Example

A minimal Django project demonstrating `openjobspec-django` integration.

## Quick Start

### 1. Start infrastructure

```bash
docker compose up -d
```

This starts Redis, an OJS server (Redis backend), and PostgreSQL.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
python manage.py migrate
```

### 4. Start the OJS worker (separate terminal)

```bash
python manage.py ojs_worker --queues default,email
```

### 5. Start the Django dev server (separate terminal)

```bash
python manage.py runserver
```

### 6. Enqueue a job

```bash
curl -X POST http://localhost:8000/enqueue/ \
  -H "Content-Type: application/json" \
  -d '{"to": "user@example.com", "template": "welcome"}'
```

The worker terminal should log the job being processed.

## Cleanup

```bash
docker compose down
```
