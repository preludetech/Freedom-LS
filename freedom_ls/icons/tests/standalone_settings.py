"""Minimal Django settings for running the icons app's tests with no host project."""

SECRET_KEY = "semantic-icons-standalone-tests"  # noqa: S105  # pragma: allowlist secret
DATABASES: dict[str, dict[str, str]] = {}
INSTALLED_APPS = ["django_cotton.apps.SimpleAppConfig", "freedom_ls.icons"]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "OPTIONS": {
            "loaders": [
                "django_cotton.cotton_loader.Loader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": ["django.template.context_processors.request"],
            "builtins": ["django_cotton.templatetags.cotton"],
        },
    },
]

# The components are named with hyphens, as in a host project that keeps hyphenated file names.
COTTON_SNAKE_CASED_NAMES = False
# SEMANTIC_ICONS_ICONIFY_DIR is left unset: these tests prove the bundled data alone works.
