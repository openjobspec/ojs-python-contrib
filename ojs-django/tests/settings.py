"""Minimal Django settings for ojs_django tests."""

SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "ojs_django",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# OJS settings — dict-based format
OJS = {
    "URL": "http://localhost:8080",
    "DEFAULT_QUEUE": "default",
    "QUEUE_PREFIX": "",
    "DEFAULT_RETRY": {"max_attempts": 5, "backoff": "exponential"},
    "WORKER": {"concurrency": 10, "queues": ["default", "email"]},
}
