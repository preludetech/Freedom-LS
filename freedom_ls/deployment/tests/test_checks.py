from __future__ import annotations

import pytest

from django.core.checks import CheckMessage, registry
from django.test import override_settings

from freedom_ls.deployment.checks import (
    check_database_cache_tables_exist,
    check_media_aliases_name_their_own_bucket,
    check_media_aliases_not_on_local_disk,
    check_media_aliases_not_shared_with_default,
    check_private_media_aliases_sign_their_urls,
    check_sentry_release_set_when_dsn_set,
)
from freedom_ls.deployment.storage import build_storages
from freedom_ls.deployment.tests.conftest import LEGACY_SHARED_BUCKET_ENV, set_env


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


def _hints_by_alias(
    errors: list[CheckMessage], aliases: tuple[str, ...]
) -> dict[str, str]:
    """Each alias named in an error message, mapped to that error's hint."""
    found: dict[str, str] = {}
    for error in errors:
        assert error.hint is not None
        for alias in aliases:
            if alias in error.msg:
                found[alias] = error.hint
    return found


def test_sensitive_alias_check_is_registered_via_app_ready() -> None:
    # deploy=True checks land in registry.registry.deployment_checks rather
    # than registered_checks, so this guards against DeploymentAppConfig.ready()
    # dropping the checks import specifically for --deploy runs.
    assert (
        check_media_aliases_not_shared_with_default
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
    errors = check_media_aliases_not_shared_with_default()

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
def test_fs_alias_matching_default_is_reported_once_as_local_disk() -> None:
    # An alias on local disk is E002's, whatever 'default' points at, so this
    # configuration produces one error rather than a collision and a local-disk
    # report for the same alias.
    assert check_media_aliases_not_shared_with_default() == []

    errors = check_media_aliases_not_on_local_disk()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_deployment.E002"
    assert "user_uploads" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_USER_UPLOADS_BUCKET_NAME" in errors[0].hint


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
    errors = check_media_aliases_not_shared_with_default()

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
    errors = check_media_aliases_not_shared_with_default()

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
    errors = check_media_aliases_not_shared_with_default()

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
    # Both failure modes at once: 'public' and 'certificates' collide with
    # 'default', while 'user_uploads' and 'reports' fell back to local disk with
    # 'default' on S3. Every offending alias is reported once, by whichever
    # check owns its failure, each naming its own per-bucket variable — so an
    # operator's first --deploy lists the whole job.
    errors = check_media_aliases_not_shared_with_default()
    errors += check_media_aliases_not_on_local_disk()

    reported = _hints_by_alias(
        errors, ("public", "certificates", "user_uploads", "reports")
    )
    assert len(errors) == 4
    assert set(reported) == {"public", "certificates", "user_uploads", "reports"}
    assert "AWS_S3_PUBLIC_BUCKET_NAME" in reported["public"]
    assert "AWS_S3_CERTIFICATES_BUCKET_NAME" in reported["certificates"]
    assert "AWS_S3_USER_UPLOADS_BUCKET_NAME" in reported["user_uploads"]
    assert "AWS_S3_GENERATED_BUCKET_NAME" in reported["reports"]


def test_intended_production_configuration_returns_no_errors(
    production_env: None,
) -> None:
    storages_dict = build_storages(
        staticfiles={
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    )

    with override_settings(STORAGES=storages_dict, DEBUG=False):
        errors = check_media_aliases_not_shared_with_default()

    assert errors == []


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "public": _s3_entry("fls-public", "https://s3.example.com"),
        "course_media": _s3_entry("fls-course-media", "https://s3.example.com"),
        "user_uploads": _s3_entry("fls-user-data", "https://s3.example.com"),
        "certificates": _s3_entry("fls-public", "https://s3.example.com"),
        "reports": _fs_entry(),
    },
    DEBUG=False,
)
def test_fs_alias_with_s3_default_and_debug_false_returns_error() -> None:
    # The typo case section 5.3 promises is caught: the shared
    # AWS_STORAGE_BUCKET_NAME is unset and AWS_S3_GENERATED_BUCKET_NAME is
    # misspelled, so 'reports' drops to local disk while 'default' keeps its own
    # bucket. Comparing against 'default' alone finds a difference and lets it
    # through, which is how learner report PDFs reach a container's local disk.
    assert check_media_aliases_not_shared_with_default() == []

    errors = check_media_aliases_not_on_local_disk()

    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_deployment.E002"
    assert "reports" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_GENERATED_BUCKET_NAME" in errors[0].hint


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "public": _s3_entry("fls-public", "https://s3.example.com"),
        "course_media": _s3_entry("fls-course-media", "https://s3.example.com"),
        "user_uploads": _s3_entry("fls-user-data", "https://s3.example.com"),
        "certificates": _s3_entry("fls-public", "https://s3.example.com"),
        "reports": _fs_entry(),
    },
    DEBUG=True,
)
def test_fs_alias_with_s3_default_and_debug_true_returns_no_errors() -> None:
    # Same configuration under DEBUG=True. A developer running --deploy locally
    # must not be flagged. A staging environment deliberately on local disk sets
    # DEBUG=False, and silences E002 without giving up the collision check.
    assert check_media_aliases_not_on_local_disk() == []


@override_settings(
    STORAGES={
        "default": _fs_entry(),
        "public": _fs_entry(),
        "course_media": _fs_entry(),
        "user_uploads": _fs_entry(),
        "certificates": _fs_entry(),
        "reports": _fs_entry(),
    },
    DEBUG=False,
)
def test_every_alias_on_local_disk_reports_each_alias_once() -> None:
    # A downstream project's first --deploy with no AWS_* variable set. Each of
    # the five media aliases is reported once, and no alias is reported twice
    # for being both local disk and identical to 'default'.
    assert check_media_aliases_not_shared_with_default() == []

    errors = check_media_aliases_not_on_local_disk()

    assert len(errors) == 5
    assert {error.id for error in errors} == {"freedom_ls_deployment.E002"}
    for alias in ("public", "course_media", "user_uploads", "certificates", "reports"):
        assert sum(alias in error.msg for error in errors) == 1


def test_local_disk_check_is_registered_via_app_ready() -> None:
    assert check_media_aliases_not_on_local_disk in registry.registry.deployment_checks


@override_settings(
    STORAGES={
        "default": _s3_entry("fls-default", "https://s3.example.com"),
        "course_media": _fs_entry(),
        "user_uploads": _fs_entry(),
        "certificates": _fs_entry(),
        "reports": _fs_entry(),
    },
    DEBUG=False,
)
def test_local_disk_check_skips_an_undeclared_alias() -> None:
    # "public" is missing from STORAGES. E001 owns that report; E002 must skip
    # the alias rather than let InvalidStorageError escape or duplicate it.
    errors = check_media_aliases_not_on_local_disk()

    assert len(errors) == 4
    assert all("public" not in error.msg for error in errors)


def test_intended_production_configuration_is_not_on_local_disk(
    production_env: None,
) -> None:
    storages_dict = build_storages(
        staticfiles={
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    )

    with override_settings(STORAGES=storages_dict, DEBUG=False):
        errors = check_media_aliases_not_on_local_disk()

    assert errors == []


def _storages_from_env(**alias_names: str) -> dict[str, dict[str, object]]:
    """The real STORAGES dict the current environment resolves to."""
    return build_storages(staticfiles={"BACKEND": "some.backend"}, **alias_names)


def test_own_bucket_check_is_registered_via_app_ready() -> None:
    assert (
        check_media_aliases_name_their_own_bucket in registry.registry.deployment_checks
    )


def test_alias_that_inherited_the_shared_bucket_returns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_env(monkeypatch, LEGACY_SHARED_BUCKET_ENV)

    with override_settings(STORAGES=_storages_from_env()):
        errors = check_media_aliases_name_their_own_bucket()

    assert [error.id for error in errors] == ["freedom_ls_deployment.E003"]
    assert "reports" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_GENERATED_BUCKET_NAME" in errors[0].hint


def test_the_inherited_bucket_is_invisible_to_the_other_two_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hole E003 fills. With `default` on a bucket of its own, an alias that
    fell through to the shared name matches neither of the other rules: the
    identities differ, so E001 is silent, and the alias is on S3, so E002 skips
    it. Cohort report PDFs land in the public bucket with a clean check."""
    set_env(monkeypatch, LEGACY_SHARED_BUCKET_ENV)

    with override_settings(STORAGES=_storages_from_env(), DEBUG=False):
        assert check_media_aliases_not_shared_with_default() == []
        assert check_media_aliases_not_on_local_disk() == []


def test_intended_production_configuration_names_its_own_buckets(
    production_env: None,
) -> None:
    with override_settings(STORAGES=_storages_from_env()):
        assert check_media_aliases_name_their_own_bucket() == []


def test_unset_shared_bucket_name_returns_no_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_env(monkeypatch, {"AWS_S3_PUBLIC_BUCKET_NAME": "fls-prod-public"})

    with override_settings(STORAGES=_storages_from_env()):
        assert check_media_aliases_name_their_own_bucket() == []


def test_hand_built_storages_matching_no_variable_returns_no_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A project that builds STORAGES itself never becomes a false positive: the
    check fires only when the resolved bucket is the value the shared variable
    holds."""
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    with override_settings(
        STORAGES={
            "default": _s3_entry("hand-built-default"),
            "public": _s3_entry("hand-built-public"),
            "course_media": _s3_entry("hand-built-course-media"),
            "user_uploads": _s3_entry("hand-built-user-data"),
            "certificates": _s3_entry("hand-built-public"),
            "reports": _s3_entry("hand-built-user-data"),
        }
    ):
        assert check_media_aliases_name_their_own_bucket() == []


def test_signing_check_is_registered_via_app_ready() -> None:
    assert (
        check_private_media_aliases_sign_their_urls
        in registry.registry.deployment_checks
    )


def test_shared_querystring_auth_off_reports_every_private_alias(
    production_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shared form reaches all five media aliases. A project upgrading from
    the single-bucket layout carries it forward and turns report PDFs naming
    learners into permanently public URLs."""
    monkeypatch.setenv("AWS_QUERYSTRING_AUTH", "false")

    with override_settings(STORAGES=_storages_from_env()):
        errors = check_private_media_aliases_sign_their_urls()

    assert {error.id for error in errors} == {"freedom_ls_deployment.E004"}
    assert set(
        _hints_by_alias(errors, ("course_media", "user_uploads", "reports"))
    ) == {"course_media", "user_uploads", "reports"}
    assert len(errors) == 3


def test_anonymously_readable_aliases_may_serve_unsigned(production_env: None) -> None:
    with override_settings(STORAGES=_storages_from_env()):
        assert check_private_media_aliases_sign_their_urls() == []


def test_one_private_alias_opting_out_is_reported_on_its_own(
    production_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_S3_GENERATED_QUERYSTRING_AUTH", "false")

    with override_settings(STORAGES=_storages_from_env()):
        errors = check_private_media_aliases_sign_their_urls()

    assert len(errors) == 1
    assert "reports" in errors[0].msg
    assert errors[0].hint is not None
    assert "AWS_S3_GENERATED_QUERYSTRING_AUTH" in errors[0].hint


def test_a_media_alias_on_local_disk_is_not_reported_as_unsigned() -> None:
    """Local disk has no signing to lose. E002 owns that whole class."""
    with override_settings(
        STORAGES={
            "default": _fs_entry(),
            "public": _fs_entry(),
            "course_media": _fs_entry(),
            "user_uploads": _fs_entry(),
            "certificates": _fs_entry(),
            "reports": _fs_entry(),
        }
    ):
        assert check_private_media_aliases_sign_their_urls() == []


@override_settings(
    ORGANISATION_LOGO_STORAGE_ALIAS="branding",
    CONTENT_MEDIA_STORAGE_ALIAS="courseware",
    REPORTS_STORAGE_ALIAS="generated_reports",
)
def test_every_check_reads_the_aliases_under_their_configured_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing may hardcode an alias name a setting owns. A project that renames
    one would otherwise be checked on keys that no longer exist."""
    set_env(monkeypatch, LEGACY_SHARED_BUCKET_ENV)
    monkeypatch.setenv("AWS_QUERYSTRING_AUTH", "false")
    renamed = _storages_from_env(
        logo_alias="branding",
        content_media_alias="courseware",
        reports_alias="generated_reports",
    )

    with override_settings(STORAGES=renamed, DEBUG=False):
        own_bucket_errors = check_media_aliases_name_their_own_bucket()
        signing_errors = check_private_media_aliases_sign_their_urls()
        assert check_media_aliases_not_shared_with_default() == []
        assert check_media_aliases_not_on_local_disk() == []

    assert [error.id for error in own_bucket_errors] == ["freedom_ls_deployment.E003"]
    assert "generated_reports" in own_bucket_errors[0].msg
    assert set(
        _hints_by_alias(
            signing_errors, ("courseware", "user_uploads", "generated_reports")
        )
    ) == {"courseware", "user_uploads", "generated_reports"}


DB_CACHE_TABLE = "test_django_cache_table"


def _db_cache(table: str) -> dict[str, dict[str, str]]:
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": table,
        }
    }


def test_database_cache_check_is_registered_via_app_ready() -> None:
    assert check_database_cache_tables_exist in registry.registry.deployment_checks


@pytest.mark.django_db
def test_database_cache_without_its_table_returns_one_e005() -> None:
    with override_settings(CACHES=_db_cache("no_such_cache_table")):
        errors = check_database_cache_tables_exist()

    assert [error.id for error in errors] == ["freedom_ls_deployment.E005"]
    assert "no_such_cache_table" in errors[0].msg
    hint = errors[0].hint
    assert hint is not None
    assert "createcachetable" in hint


@pytest.mark.django_db
def test_database_cache_with_its_table_returns_no_errors() -> None:
    from django.core.management import call_command

    with override_settings(CACHES=_db_cache(DB_CACHE_TABLE)):
        call_command("createcachetable", verbosity=0)

        assert check_database_cache_tables_exist() == []


@pytest.mark.django_db
def test_cache_that_is_not_database_backed_returns_no_errors() -> None:
    locmem = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

    with override_settings(CACHES=locmem):
        assert check_database_cache_tables_exist() == []
