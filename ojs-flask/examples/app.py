"""Example Flask application with OJS integration."""

from flask import Flask, jsonify, request

from ojs_flask import OJS, enqueue

app = Flask(__name__)
app.config["OJS_URL"] = "http://localhost:8080"

ojs_ext = OJS(app)


@app.post("/emails")
def send_email():
    """Enqueue an email delivery job."""
    data = request.get_json()
    job = enqueue(
        "email.send",
        [data["to"], data["subject"], data["body"]],
        queue="email",
        meta={"triggered_by": "api"},
    )
    return jsonify({"job_id": job.id, "state": job.state}), 202


@app.post("/reports")
def generate_report():
    """Enqueue a report generation job using the extension directly."""
    data = request.get_json()
    job = ojs_ext.enqueue(
        "report.generate",
        [data["report_type"]],
        queue="reports",
        meta={"user_id": data.get("user_id")},
    )
    return jsonify({"job_id": job.id, "state": job.state}), 202


@app.get("/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
