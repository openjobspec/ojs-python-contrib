"""Flask blueprint providing OJS health check endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify


def create_health_blueprint(url_prefix: str = "/ojs") -> Blueprint:
    """Create a Flask blueprint with OJS health check endpoints.

    Args:
        url_prefix: URL prefix for all routes in the blueprint.
            Defaults to ``/ojs``.

    Returns:
        A :class:`~flask.Blueprint` instance with ``/health`` and
        ``/status`` endpoints.

    Example::

        from ojs_flask import create_health_blueprint

        app = Flask(__name__)
        app.register_blueprint(create_health_blueprint())
    """
    bp = Blueprint("ojs_health", __name__, url_prefix=url_prefix)

    @bp.route("/health")
    def health():  # type: ignore[return-value]
        """Health check endpoint that pings the OJS server."""
        from ojs_flask.helpers import get_client

        try:
            client = get_client()
            queues = client.list_queues()
            return jsonify({"status": "healthy", "queues": len(queues)}), 200
        except Exception as exc:
            return jsonify({"status": "unhealthy", "error": str(exc)}), 503

    @bp.route("/status")
    def status():  # type: ignore[return-value]
        """Detailed OJS status with queue statistics."""
        from ojs_flask.helpers import get_client

        try:
            client = get_client()
            queues = client.list_queues()
            queue_info = []
            for q in queues:
                try:
                    stats = client.queue_stats(q)
                    queue_info.append({"name": q, "stats": stats})
                except Exception:
                    queue_info.append({"name": q, "stats": None})
            return jsonify({
                "status": "healthy",
                "queues": queue_info,
            }), 200
        except Exception as exc:
            return jsonify({"status": "unhealthy", "error": str(exc)}), 503

    return bp
