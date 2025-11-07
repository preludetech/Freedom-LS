from .settings_base import *
import sys
import os

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-j7(y+5*bk359kji$691f-gpevyhm*id37y_)7me%scmurdd&pv"


AUTH_PASSWORD_VALIDATORS = []


INTERNAL_IPS = [
    # ...
    "127.0.0.1",
    # ...
]

TESTING = "test" in sys.argv or "PYTEST_VERSION" in os.environ

if not TESTING:
    INSTALLED_APPS = [
        *INSTALLED_APPS,
        "debug_toolbar",
    ]
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        *MIDDLEWARE,
    ]

INSTALLED_APPS = [*INSTALLED_APPS, "django_browser_reload"]


####
# ALLAUTH

ACCOUNT_RATE_LIMITS = False
HEADLESS_SERVE_SPECIFICATION = True
