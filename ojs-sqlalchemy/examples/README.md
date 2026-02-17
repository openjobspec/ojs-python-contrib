# ojs-sqlalchemy Examples

## Setup

1. Start the OJS server and Redis:

```bash
docker compose up -d
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the example:

```bash
python main.py
```

## What the Example Does

- **Example 1** — Creates a user and enqueues a welcome email job using `enqueue_after_commit()`. The job is sent to OJS only when the database transaction commits.
- **Example 2** — Creates a user and writes a job to the outbox table atomically. A separate publisher process reads the outbox and delivers jobs to OJS.
