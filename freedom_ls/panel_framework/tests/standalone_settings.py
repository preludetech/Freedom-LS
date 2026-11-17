"""Minimal Django settings for running the framework's unit tests with no host project."""

from __future__ import annotations

from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent

SECRET_KEY = "panel-framework-standalone-tests"  # noqa: S105  # pragma: allowlist secret
DEBUG = False
TIME_ZONE = "UTC"
USE_TZ = True
ALLOWED_HOSTS = ["testserver"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.admin",
    "django_cotton.apps.SimpleAppConfig",
    "freedom_ls.panel_framework",
    "freedom_ls.panel_framework.tests.standalone_app",
]

# The admin's system checks require these three.
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

AUTH_USER_MODEL = "standalone_app.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(_TESTS_DIR / "standalone_templates")],
        "OPTIONS": {
            "loaders": [
                "django_cotton.cotton_loader.Loader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "freedom_ls.panel_framework.tests.standalone_app.context_processors.site_name",
            ],
            "builtins": ["django_cotton.templatetags.cotton"],
        },
    },
]

TASKS = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}

# The components are named with hyphens, as in a host project that keeps hyphenated file names.
COTTON_SNAKE_CASED_NAMES = False

ROOT_URLCONF = "freedom_ls.panel_framework.tests.root_urls"
