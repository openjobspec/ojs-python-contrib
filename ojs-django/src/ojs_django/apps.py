"""Django AppConfig for ojs_django."""

from __future__ import annotations

from django.apps import AppConfig
from django.core.checks import Error, register


class OjsDjangoConfig(AppConfig):
    """Django application configuration for OJS integration."""

    name = "ojs_django"
    default_auto_field = "django.db.models.BigAutoField"
    verbose_name = "Open Job Spec"

    def ready(self) -> None:
        _register_checks()


def _register_checks() -> None:
    @register("ojs")
    def check_ojs_settings(**kwargs: object) -> list[Error]:  # noqa: ARG001
        from django.conf import settings

        errors: list[Error] = []
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
