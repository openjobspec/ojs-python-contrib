"""Django AppConfig for ojs_django."""

from __future__ import annotations

import importlib
import logging
import signal
from typing import Any

from django.apps import AppConfig
from django.core.checks import Error, register

logger = logging.getLogger("ojs_django")


class OjsDjangoConfig(AppConfig):
    """Django application configuration for OJS integration."""

    name = "ojs_django"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Open Job Spec"

    def ready(self) -> None:
        _register_checks()
        self._autodiscover_jobs()
        self._register_shutdown_handlers()

    def _autodiscover_jobs(self) -> None:
        """Auto-discover ``jobs.py`` modules in all installed apps.

        This ensures that ``@ojs_job`` decorators are executed at startup,
        registering all handlers before the worker starts.
        """
        from django.apps import apps

        for app_config in apps.get_app_configs():
            module_name = f"{app_config.name}.jobs"
            try:
                importlib.import_module(module_name)
                logger.debug("Discovered job handlers in %s", module_name)
            except ImportError:
                pass  # App has no jobs.py — that's fine

    @staticmethod
    def _register_shutdown_handlers() -> None:
        """Register signal handlers for graceful shutdown.

        Closes the shared OJS client on SIGTERM/SIGINT to release
        connections cleanly.
        """

        def _shutdown_handler(signum: int, frame: Any) -> None:
            from ojs_django.backend import reset_client

            logger.info("Received signal %s, cleaning up OJS client", signal.Signals(signum).name)
            reset_client()

        for sig in (signal.SIGTERM, signal.SIGINT):
            existing = signal.getsignal(sig)
            if existing in (signal.SIG_DFL, signal.SIG_IGN, None):
                signal.signal(sig, _shutdown_handler)


def _register_checks() -> None:
    @register("ojs")
    def check_ojs_settings(**kwargs: object) -> list[Error]:
        from django.conf import settings

        errors: list[Error] = []

        # Check dict-based config
        ojs_dict = getattr(settings, "OJS", None)
        if ojs_dict is not None:
            if not isinstance(ojs_dict, dict):
                errors.append(
                    Error(
                        "OJS must be a dict.",
                        id="ojs.E001",
                    )
                )
                return errors

            url = ojs_dict.get("URL")
            if url is not None and not isinstance(url, str):
                errors.append(
                    Error(
                        "OJS['URL'] must be a string.",
                        id="ojs.E002",
                    )
                )

            worker = ojs_dict.get("WORKER", {})
            if not isinstance(worker, dict):
                errors.append(
                    Error(
                        "OJS['WORKER'] must be a dict.",
                        id="ojs.E003",
                    )
                )
            return errors

        # Check legacy flat settings
        url = getattr(settings, "OJS_URL", None)
        if url is not None and not isinstance(url, str):
            errors.append(
                Error(
                    "OJS_URL must be a string.",
                    id="ojs.E001",
                )
            )
        queues = getattr(settings, "OJS_QUEUES", None)
        if queues is not None and not isinstance(queues, list):
            errors.append(
                Error(
                    "OJS_QUEUES must be a list of strings.",
                    id="ojs.E002",
                )
            )
        return errors
