"""Django settings for the OJS example project."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-example-only-change-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "ojs_django",
    "myproject",
]

ROOT_URLCONF = "myproject.urls"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "myproject",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- OJS Configuration ---
OJS_URL = "http://localhost:8080"
OJS_QUEUES = ["default", "email"]
OJS_CONCURRENCY = 10
OJS_POLL_INTERVAL = 2.0
