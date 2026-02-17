# ojs-flask Example

A minimal Flask application demonstrating OJS integration for background job processing.

## Prerequisites

- Python 3.11+
- Docker & Docker Compose

## Running

1. **Start the OJS backend:**

   ```bash
   docker compose up -d
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask app:**

   ```bash
   python app.py
   ```

4. **Enqueue a job:**

   ```bash
   curl -X POST http://localhost:5000/emails \
     -H "Content-Type: application/json" \
     -d '{"to": "user@example.com", "subject": "Hello", "body": "World"}'
   ```

5. **Enqueue a report:**

   ```bash
   curl -X POST http://localhost:5000/reports \
     -H "Content-Type: application/json" \
     -d '{"report_type": "monthly", "user_id": "u-123"}'
   ```

## Teardown

```bash
docker compose down
```
