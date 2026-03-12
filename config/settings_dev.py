import os
import sys

from freedom_ls.base.git_utils import branch_to_db_name, get_current_branch

from .settings_base import *  # noqa: F403

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-j7(y+5*bk359kji$691f-gpevyhm*id37y_)7me%scmurdd&pv"  # noqa: S105


AUTH_PASSWORD_VALIDATORS = []


INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

TESTING = "test" in sys.argv or "PYTEST_VERSION" in os.environ

if not TESTING:
    INSTALLED_APPS = [
        *INSTALLED_APPS,  # noqa: F405
        "debug_toolbar",
    ]
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        *MIDDLEWARE,  # noqa: F405
    ]

INSTALLED_APPS = [
    *INSTALLED_APPS,
    # "django_watchfiles",
    "django_browser_reload",
    "freedom_ls.qa_helpers",
]

_template_options = TEMPLATES[0]["OPTIONS"]  # noqa: F405
_context_processors: list[str] = _template_options["context_processors"]  # type: ignore[index]
_context_processors.append("freedom_ls.base.context_processors.debug_branch_info")


####
# ALLAUTH

ACCOUNT_RATE_LIMITS = False
HEADLESS_SERVE_SPECIFICATION = True


###
# EMAIL

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "gitignore/emails"


#####
# DATABASE

_branch = get_current_branch(base_dir=BASE_DIR)  # noqa: F405
_db_name = branch_to_db_name(_branch) if _branch else "db"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": "pguser",
        "NAME": _db_name,
        "PASSWORD": "password",  # pragma: allowlist secret
        "HOST": "127.0.0.1",
        "PORT": "6543",
        "TEST": {"name": f"test_{_db_name}"},
    },
}


MIDDLEWARE = [*MIDDLEWARE, "django_browser_reload.middleware.BrowserReloadMiddleware"]


#####
# ROLE-BASED PERMISSIONS

FREEDOMLS_PERMISSIONS_MODULES = {
    "DemoDev": "config.role_based_permissions.demodev",
}

FORCE_SITE_NAME = "DemoDev"
