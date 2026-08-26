from __future__ import annotations

from django.core.checks import registry
from django.test import override_settings

from freedom_ls.deployment.checks import (
    check_sensitive_aliases_not_shared_with_default,
    check_sentry_release_set_when_dsn_set,
)
from freedom_ls.deployment.storage import build_storages


def test_check_is_registered_via_app_ready() -> None:
    # Guards against DeploymentAppConfig.ready() dropping the checks import: the
    # direct-call tests below would stay green even if the check were never
    # registered and so never ran on manage.py check / migrate.
    assert check_sentry_release_set_when_dsn_set in registry.registry.registered_checks


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0", SENTRY_RELEASE=None
)
def test_dsn_set_and_release_unset_returns_one_warning() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert len(warnings) == 1
    assert warnings[0].id == "freedom_ls_deployment.W001"


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0", SENTRY_RELEASE=""
)
def test_dsn_set_and_release_empty_string_returns_one_warning() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert len(warnings) == 1
    assert warnings[0].id == "freedom_ls_deployment.W001"


@override_settings(
    SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0",
    SENTRY_RELEASE="fls@1.2.3",
)
def test_dsn_set_and_release_set_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []


@override_settings(SENTRY_DSN=None, SENTRY_RELEASE=None)
def test_dsn_unset_and_release_unset_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []


@override_settings(SENTRY_DSN=None, SENTRY_RELEASE="fls@1.2.3")
def test_dsn_unset_and_release_set_returns_no_warnings() -> None:
    warnings = check_sentry_release_set_when_dsn_set(None)

    assert warnings == []


def _s3_entry(bucket_name: str, endpoint_url: str | None = None) -> dict[str, object]:
    """A STORAGES entry pointing at an S3-compatible bucket, for test fixtures."""
    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {"bucket_name": bucket_name, "endpoint_url": endpoint_url},
    }


def _fs_entry(location: str | None = None) -> dict[str, object]:
    """A STORAGES entry pointing at local disk, for test fixtures."""
    options: dict[str, object] = {"location": location} if location else {}
    return {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": options,
    }


_UNCOMPARABLE_ENTRY: dict[str, object] = {
    "BACKEND": "django.core.files.storage.memory.InMemoryStorage",
}


def test_sensitive_alias_check_is_registered_via_app_ready() -> None:
    # deploy=True checks land in registry.registry.deployment_checks rather
    # than registered_checks, so this guards against DeploymentAppConfig.ready()
    # dropping the checks import specifically for --deploy runs.
    assert (
        check_sensitive_aliases_not_shared_with_default
        in registry.registry.deployment_checks
    )


@override_settings(
    STORAGES={
        "default": _s3_entry("shared-bucket", "https://s3.example.com"),
        "public": _s3_entry("shared-bucket", "https://s3.example.com"),
        "course_media": _fs_entry(),
        "user_uploads": _fs_entry(),
        "certificates": _fs_entry(),
        "reports": _fs_entry(),
    },
    DEBUG=True,
)
def test_media_alias_matching_default_s3_identity_returns_error() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_deployment.E001"
    assert "public" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_PUBLIC_BUCKET_NAME" in errors[0].hint


@override_settings(
    STORAGES={
        "default": _fs_entry("/data/shared"),
        "user_uploads": _fs_entry("/data/shared"),
        "public": _s3_entry("bucket-public"),
        "course_media": _s3_entry("bucket-course-media"),
        "certificates": _s3_entry("bucket-certificates"),
        "reports": _s3_entry("bucket-reports"),
    },
    DEBUG=False,
)
def test_fs_alias_matching_default_with_debug_false_returns_error() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_deployment.E001"
    assert "user_uploads" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_USER_UPLOADS_BUCKET_NAME" in errors[0].hint


@override_settings(
    STORAGES={
        "default": _fs_entry("/data/shared"),
        "user_uploads": _fs_entry("/data/shared"),
        "public": _s3_entry("bucket-public"),
        "course_media": _s3_entry("bucket-course-media"),
        "certificates": _s3_entry("bucket-certificates"),
        "reports": _s3_entry("bucket-reports"),
    },
    DEBUG=True,
)
def test_fs_alias_matching_default_with_debug_true_returns_no_errors() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert errors == []


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "public": _s3_entry("fls-public", "https://s3.example.com"),
        "course_media": _s3_entry("fls-course-media", "https://s3.example.com"),
        "user_uploads": _s3_entry("fls-user-uploads", "https://s3.example.com"),
        "certificates": _s3_entry("fls-certificates", "https://s3.example.com"),
        "reports": _s3_entry("fls-reports", "https://s3.example.com"),
    },
    DEBUG=False,
)
def test_media_aliases_with_distinct_buckets_return_no_errors() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert errors == []


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "public": _s3_entry("fls-public", "https://s3.example.com"),
        "course_media": _s3_entry("fls-course-media", "https://s3.example.com"),
        "user_uploads": _s3_entry("fls-user-uploads", "https://s3.example.com"),
        "certificates": _UNCOMPARABLE_ENTRY,
        "reports": _s3_entry("fls-reports", "https://s3.example.com"),
    },
    DEBUG=False,
)
def test_media_alias_on_uncomparable_backend_returns_no_errors() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert errors == []


@override_settings(
    STORAGES={
        "default": _fs_entry(),
        "course_media": _fs_entry(),
        "user_uploads": _fs_entry(),
        "certificates": _fs_entry(),
        "reports": _fs_entry(),
    },
    DEBUG=True,
)
def test_undeclared_media_alias_returns_error_instead_of_raising() -> None:
    # "public" is intentionally missing from STORAGES: storages["public"] would
    # raise InvalidStorageError, and the check must turn that into an E001
    # rather than letting it escape.
    errors = check_sensitive_aliases_not_shared_with_default()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_deployment.E001"
    assert "public" in errors[0].msg


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "public": _s3_entry("fls-default", "https://s3.example.com"),
        "course_media": _s3_entry("fls-course-media", "https://s3.example.com"),
        "user_uploads": _fs_entry(),
        "certificates": _s3_entry("fls-default", "https://s3.example.com"),
        "reports": _fs_entry(),
    },
    DEBUG=False,
)
def test_multiple_offending_aliases_each_produce_their_own_error() -> None:
    errors = check_sensitive_aliases_not_shared_with_default()

    assert len(errors) == 2
    assert errors[0].id == "freedom_ls_deployment.E001"
    assert "public" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_PUBLIC_BUCKET_NAME" in errors[0].hint
    assert errors[1].id == "freedom_ls_deployment.E001"
    assert "certificates" in errors[1].msg
    assert errors[1].hint is not None
    assert "AWS_S3_CERTIFICATES_BUCKET_NAME" in errors[1].hint


def test_intended_production_configuration_returns_no_errors(
    production_env: None,
) -> None:
    storages_dict = build_storages(
        staticfiles={
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    )

    with override_settings(STORAGES=storages_dict, DEBUG=False):
        errors = check_sensitive_aliases_not_shared_with_default()

    assert errors == []
