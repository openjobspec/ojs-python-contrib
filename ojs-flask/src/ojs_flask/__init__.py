"""Flask integration for Open Job Spec (OJS)."""

from ojs_flask.cli import ojs_cli
from ojs_flask.extension import OJS
from ojs_flask.health import create_health_blueprint
from ojs_flask.helpers import enqueue, get_client
from ojs_flask.worker import FlaskOJSWorker

__version__ = "0.9.0"
__all__ = [
    "OJS",
    "enqueue",
    "get_client",
    "ojs_cli",
    "create_health_blueprint",
    "FlaskOJSWorker",
]

