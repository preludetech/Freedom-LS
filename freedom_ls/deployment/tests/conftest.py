from __future__ import annotations

import os

import pytest

#: Every key build_storages emits and settings.STORAGES declares.
EXPECTED_ALIASES = {
    "default",
    "staticfiles",
    "public",
    "course_media",
    "user_uploads",
    "reports",
    "certificates",
}


#: The intended production environment: three buckets across six purpose
#: variables, with the shared AWS_STORAGE_BUCKET_NAME left unset so every
#: alias names its own bucket rather than falling through to one.
PRODUCTION_ENV: dict[str, str] = {
    "AWS_S3_PUBLIC_BUCKET_NAME": "fls-prod-public",
    "AWS_S3_CERTIFICATES_BUCKET_NAME": "fls-prod-public",
    "AWS_S3_COURSE_MEDIA_BUCKET_NAME": "fls-prod-course-media",
    "AWS_S3_GENERATED_BUCKET_NAME": "fls-prod-user-data",
    "AWS_S3_USER_UPLOADS_BUCKET_NAME": "fls-prod-user-data",
    "AWS_S3_DEFAULT_BUCKET_NAME": "fls-prod-default",
    "AWS_S3_ACCESS_KEY_ID": "shared-access-key",
    "AWS_S3_SECRET_ACCESS_KEY": "shared-secret-key",  # pragma: allowlist secret
    "AWS_S3_GENERATED_ACCESS_KEY_ID": "user-data-access-key",
    "AWS_S3_GENERATED_SECRET_ACCESS_KEY": "user-data-secret-key",  # pragma: allowlist secret
    "AWS_S3_USER_UPLOADS_ACCESS_KEY_ID": "user-data-access-key",
    "AWS_S3_USER_UPLOADS_SECRET_ACCESS_KEY": "user-data-secret-key",  # pragma: allowlist secret
    "AWS_S3_PUBLIC_CUSTOM_DOMAIN": "public.example.test",
    "AWS_S3_CERTIFICATES_CUSTOM_DOMAIN": "public.example.test",
    "AWS_S3_PUBLIC_QUERYSTRING_AUTH": "false",
    "AWS_S3_CERTIFICATES_QUERYSTRING_AUTH": "false",
}


#: The same three buckets reached the way a project upgrading from the single-bucket
#: layout reaches them: its old AWS_STORAGE_BUCKET_NAME still set, and one
#: per-purpose name — GENERATED — missing. `reports` then lands in the public
#: bucket while `default` sits on a bucket of its own, which is the configuration
#: E003 exists for.
LEGACY_SHARED_BUCKET_ENV: dict[str, str] = {
    "AWS_STORAGE_BUCKET_NAME": "fls-prod-public",
    "AWS_S3_DEFAULT_BUCKET_NAME": "fls-prod-default",
    "AWS_S3_PUBLIC_BUCKET_NAME": "fls-prod-public",
    "AWS_S3_CERTIFICATES_BUCKET_NAME": "fls-prod-public",
    "AWS_S3_COURSE_MEDIA_BUCKET_NAME": "fls-prod-course-media",
    "AWS_S3_USER_UPLOADS_BUCKET_NAME": "fls-prod-user-data",
}


@pytest.fixture(autouse=True)
def _clear_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every AWS_* variable first, so a developer's real credentials
    exported for an unrelated project never change these results."""
    for name in [name for name in os.environ if name.startswith("AWS_")]:
        monkeypatch.delenv(name, raising=False)


def set_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    """Apply every name/value pair in env via monkeypatch.setenv."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply PRODUCTION_ENV, the intended production storage configuration."""
    set_env(monkeypatch, PRODUCTION_ENV)
