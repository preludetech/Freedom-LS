from .settings_base import *  # noqa: F403, F405
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
]


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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "USER": "pguser",
        "NAME": "db",
        "PASSWORD": "password",
        "HOST": "127.0.0.1",
        "PORT": "6543",
    },
}


MIDDLEWARE = MIDDLEWARE + ["django_browser_reload.middleware.BrowserReloadMiddleware"]

# TODO: DELETE

# AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_ACCESS_KEY_ID = os.getenv("AWS_S3_ACCESS_KEY_ID")
# AWS_S3_SECRET_ACCESS_KEY = os.getenv("AWS_S3_SECRET_ACCESS_KEY")
# AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
# AWS_DEFAULT_ACL = os.getenv("AWS_DEFAULT_ACL")
# AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

# default_storage = {
#     "BACKEND": "storages.backends.s3.S3Storage",
#     # "BACKEND": "storages.backends.s3.S3Storage",
#     # storages.backends.s3boto3.S3Boto3Storage
#     "OPTIONS": {
#         "bucket_name": AWS_STORAGE_BUCKET_NAME,
#         "access_key": AWS_S3_ACCESS_KEY_ID,
#         "secret_key": AWS_S3_SECRET_ACCESS_KEY,
#         "endpoint_url": AWS_S3_ENDPOINT_URL,
#         "region_name": AWS_S3_REGION_NAME,
#         "default_acl": AWS_DEFAULT_ACL,
#         "signature_version": "s3v4",
#     },
# }

# STORAGES = {
#     "default": default_storage,
#     "staticfiles": {
#         # "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#         "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
#     },
# }
