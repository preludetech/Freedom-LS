from __future__ import annotations

import os

import pytest
from botocore.config import Config

from django.core.files.base import ContentFile

from freedom_ls.deployment.storage import (
    OverwritingFileSystemStorage,
    build_s3_media_storage,
    build_storages,
)
from freedom_ls.deployment.tests.conftest import PRODUCTION_ENV

EXPECTED_ALIASES = {
    "default",
    "staticfiles",
    "public",
    "course_media",
    "user_uploads",
    "reports",
    "certificates",
}


@pytest.fixture(autouse=True)
def _clear_aws_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear every AWS_* variable first, so a developer's real credentials
    exported for an unrelated project never change these results."""
    _clear_env_prefix(monkeypatch, "AWS_")


def _clear_env_prefix(monkeypatch: pytest.MonkeyPatch, prefix: str) -> None:
    """Delete every currently-set env var whose name starts with prefix."""
    for name in [name for name in os.environ if name.startswith(prefix)]:
        monkeypatch.delenv(name, raising=False)


def _set_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    """Apply every name/value pair in env via monkeypatch.setenv."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def _build_options(
    *,
    region_name: str | None = None,
    custom_domain: str | None = None,
    querystring_auth: bool = True,
    querystring_expire: int = 3600,
) -> dict[str, object]:
    result = build_s3_media_storage(
        bucket_name="fls-media",
        access_key="AKIA_TEST",
        secret_key="secret",  # pragma: allowlist secret
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        region_name=region_name,
        custom_domain=custom_domain,
        querystring_auth=querystring_auth,
        querystring_expire=querystring_expire,
    )
    options = result["OPTIONS"]
    assert isinstance(options, dict)
    return options


def test_private_default_has_no_custom_domain_and_signed_urls() -> None:
    options = _build_options(querystring_auth=True, custom_domain=None)

    assert options["querystring_auth"] is True
    assert "custom_domain" not in options
    assert "default_acl" not in options


def test_public_opt_in_sets_custom_domain_and_disables_querystring_auth() -> None:
    options = _build_options(custom_domain="cdn.example.test", querystring_auth=False)

    assert options["custom_domain"] == "cdn.example.test"
    assert options["querystring_auth"] is False


def test_unset_region_defaults_to_auto() -> None:
    options = _build_options(region_name=None)

    assert options["region_name"] == "auto"


def test_explicit_region_is_passed_through_unchanged() -> None:
    options = _build_options(region_name="weur")

    assert options["region_name"] == "weur"


def test_client_config_disables_checksum_headers_r2_rejects() -> None:
    options = _build_options()

    client_config = options["client_config"]
    assert isinstance(client_config, Config)
    assert client_config.request_checksum_calculation == "when_required"
    assert client_config.response_checksum_validation == "when_required"


@pytest.mark.parametrize("file_overwrite", [True, False])
def test_file_overwrite_is_always_written_explicitly(file_overwrite: bool) -> None:
    # Never left to the django-storages default: whether a write at an existing
    # key replaces or renames is a decision this project makes per alias.
    result = build_s3_media_storage(
        bucket_name="fls-media",
        access_key="AKIA_TEST",
        secret_key="secret",  # pragma: allowlist secret
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        region_name=None,
        custom_domain=None,
        querystring_auth=True,
        querystring_expire=3600,
        file_overwrite=file_overwrite,
    )

    options = result["OPTIONS"]
    assert isinstance(options, dict)
    assert options["file_overwrite"] is file_overwrite


def test_omitted_file_overwrite_defaults_to_not_overwriting() -> None:
    result = build_s3_media_storage(
        bucket_name="fls-media",
        access_key="AKIA_TEST",
        secret_key="secret",  # pragma: allowlist secret
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        region_name=None,
        custom_domain=None,
        querystring_auth=True,
        querystring_expire=3600,
    )

    options = result["OPTIONS"]
    assert isinstance(options, dict)
    assert options["file_overwrite"] is False


def test_no_object_parameters_argument_omits_the_key() -> None:
    result = build_s3_media_storage(
        bucket_name="fls-media",
        access_key="AKIA_TEST",
        secret_key="secret",  # pragma: allowlist secret
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        region_name=None,
        custom_domain=None,
        querystring_auth=True,
        querystring_expire=3600,
    )

    options = result["OPTIONS"]
    assert isinstance(options, dict)
    assert "object_parameters" not in options


def test_given_object_parameters_land_in_options_unchanged() -> None:
    object_parameters = {"CacheControl": "public, max-age=86400"}

    result = build_s3_media_storage(
        bucket_name="fls-media",
        access_key="AKIA_TEST",
        secret_key="secret",  # pragma: allowlist secret
        endpoint_url="https://accountid.r2.cloudflarestorage.com",
        region_name=None,
        custom_domain=None,
        querystring_auth=True,
        querystring_expire=3600,
        object_parameters=object_parameters,
    )

    options = result["OPTIONS"]
    assert isinstance(options, dict)
    assert options["object_parameters"] == object_parameters


class TestOverwritingFileSystemStorage:
    """The local-disk stand-in for S3Storage's replace-at-an-existing-key
    behaviour. Stock FileSystemStorage suffixes instead, which is what left
    orphaned organisation logos behind."""

    def test_saving_over_an_existing_name_keeps_the_name(self, tmp_path) -> None:
        storage = OverwritingFileSystemStorage(location=str(tmp_path))
        storage.save("logo.png", ContentFile(b"first"))

        name = storage.save("logo.png", ContentFile(b"second"))

        assert name == "logo.png"

    def test_saving_over_an_existing_name_replaces_the_bytes(self, tmp_path) -> None:
        storage = OverwritingFileSystemStorage(location=str(tmp_path))
        storage.save("logo.png", ContentFile(b"first"))

        storage.save("logo.png", ContentFile(b"second"))

        assert (tmp_path / "logo.png").read_bytes() == b"second"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["logo.png"]

    def test_a_free_name_is_used_unchanged(self, tmp_path) -> None:
        storage = OverwritingFileSystemStorage(location=str(tmp_path))

        assert storage.save("logo.png", ContentFile(b"only")) == "logo.png"


def _options_of(entry: dict[str, object]) -> dict[str, object]:
    options = entry["OPTIONS"]
    assert isinstance(options, dict)
    return options


FILESYSTEM_ENTRY = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
OVERWRITING_FILESYSTEM_ENTRY = {
    "BACKEND": "freedom_ls.deployment.storage.OverwritingFileSystemStorage"
}


# Case 1: every alias key is present, in every configuration.


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({}, id="nothing_set"),
        pytest.param(
            {"AWS_STORAGE_BUCKET_NAME": "fls-shared"}, id="shared_bucket_only"
        ),
        pytest.param(PRODUCTION_ENV, id="production_env"),
    ],
)
def test_every_alias_key_is_always_present(
    env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_env(monkeypatch, env)

    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert set(result.keys()) == EXPECTED_ALIASES


# Case 2: a per-bucket variable wins over the shared variable.


def test_per_bucket_name_wins_over_shared_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_PUBLIC_BUCKET_NAME", "fls-public-only")

    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert _options_of(result["public"])["bucket_name"] == "fls-public-only"


# Case 3: an unset per-bucket name falls back to the shared bucket, landing on
# the same entry as default. This pins the precondition E001 targets.


def test_unset_per_bucket_name_falls_back_to_shared_and_matches_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    result = build_storages(staticfiles={"BACKEND": "some.backend"})
    public_options = _options_of(result["public"])
    default_options = _options_of(result["default"])

    assert public_options["bucket_name"] == default_options["bucket_name"]
    assert public_options["endpoint_url"] == default_options["endpoint_url"]
    assert public_options["access_key"] == default_options["access_key"]


# Case 4: neither the per-bucket nor the shared name is set.


@pytest.mark.parametrize(
    "alias", ["default", "course_media", "user_uploads", "reports", "certificates"]
)
def test_no_bucket_name_set_falls_back_to_filesystem_storage(alias: str) -> None:
    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert result[alias] == FILESYSTEM_ENTRY


def test_public_falls_back_to_the_overwriting_filesystem_storage() -> None:
    # The alias keeps S3's replace-at-an-existing-key behaviour when it drops to
    # local disk, so a replaced organisation logo does not accumulate suffixed
    # copies in development.
    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert result["public"] == OVERWRITING_FILESYSTEM_ENTRY


# Case 5: per-bucket credentials and endpoint override independently of the
# bucket name.


def test_per_bucket_credentials_and_endpoint_override_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv("AWS_S3_ENDPOINT_URL", "https://shared.example.test")
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")
    monkeypatch.setenv("AWS_S3_PUBLIC_ENDPOINT_URL", "https://public.example.test")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["bucket_name"] == "fls-shared"
    assert options["access_key"] == "public-only-key"
    assert options["endpoint_url"] == "https://public.example.test"


# Case 6: CacheControl on the two anonymously readable aliases only.


def test_public_cache_control_is_short_lived_and_not_immutable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["object_parameters"] == {"CacheControl": "public, max-age=86400"}


def test_certificates_cache_control_is_immutable_and_year_long(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["certificates"]
    )

    assert options["object_parameters"] == {
        "CacheControl": "public, max-age=31536000, immutable"
    }


@pytest.mark.parametrize("alias", ["course_media", "user_uploads", "reports"])
def test_other_media_aliases_carry_no_object_parameters(
    alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})[alias]
    )

    assert "object_parameters" not in options


# Case 6b: overwrite-at-a-stable-key, on the public alias only. It pairs with
# the cache header above — max-age=86400 rather than immutable is only correct
# for an object that can change at its key.


def test_public_alias_overwrites_at_an_existing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["file_overwrite"] is True


@pytest.mark.parametrize(
    "alias", ["default", "course_media", "user_uploads", "reports", "certificates"]
)
def test_other_aliases_never_overwrite_at_an_existing_key(
    alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})[alias]
    )

    assert options["file_overwrite"] is False


# Case 8: default resolves from its own purpose variable when set, and from
# the shared variable otherwise.


def test_default_resolves_from_its_own_bucket_name_when_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_DEFAULT_BUCKET_NAME", "fls-default-only")

    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert _options_of(result["default"])["bucket_name"] == "fls-default-only"


def test_default_resolves_from_shared_bucket_name_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert _options_of(result["default"])["bucket_name"] == "fls-shared"


@pytest.mark.parametrize(
    "alias", ["public", "course_media", "user_uploads", "reports", "certificates"]
)
def test_production_env_no_media_alias_matches_default(
    alias: str, production_env: None
) -> None:
    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert result[alias] != result["default"]


# Case 9: two purpose variables set to the same bucket name produce two
# distinct entries agreeing on bucket_name.


def test_production_env_public_and_certificates_share_bucket_but_differ_in_cache_control(
    production_env: None,
) -> None:
    result = build_storages(staticfiles={"BACKEND": "some.backend"})
    public_options = _options_of(result["public"])
    certificates_options = _options_of(result["certificates"])

    assert public_options["bucket_name"] == certificates_options["bucket_name"]
    assert (
        public_options["object_parameters"] != certificates_options["object_parameters"]
    )


def test_production_env_reports_and_user_uploads_share_bucket_and_credentials(
    production_env: None,
) -> None:
    result = build_storages(staticfiles={"BACKEND": "some.backend"})
    reports_options = _options_of(result["reports"])
    user_uploads_options = _options_of(result["user_uploads"])

    assert reports_options["bucket_name"] == user_uploads_options["bucket_name"]
    assert reports_options["access_key"] == user_uploads_options["access_key"]
    assert reports_options["secret_key"] == user_uploads_options["secret_key"]
    assert "custom_domain" not in reports_options


# Case 10: a per-bucket credential reaches only its own alias.


def test_per_bucket_access_key_reaches_only_its_own_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["access_key"] == "public-only-key"


@pytest.mark.parametrize(
    "alias", ["course_media", "user_uploads", "certificates", "reports", "default"]
)
def test_per_bucket_access_key_does_not_leak_to_other_aliases(
    alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})[alias]
    )

    assert options["access_key"] == "shared-key"


# Case 11: a non-default reports_alias emits that key, and no "reports" key.


def test_custom_reports_alias_emits_under_its_own_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    result = build_storages(
        staticfiles={"BACKEND": "some.backend"}, reports_alias="generated_reports"
    )

    assert "generated_reports" in result
    assert "reports" not in result
