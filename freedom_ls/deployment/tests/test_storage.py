from __future__ import annotations

from collections.abc import Iterator

import pytest
from botocore.config import Config

from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

from freedom_ls.deployment.storage import (
    bucket_name_for,
    build_s3_media_storage,
    build_storages,
)
from freedom_ls.deployment.tests.conftest import PRODUCTION_ENV, set_env

EXPECTED_ALIASES = {
    "default",
    "staticfiles",
    "public",
    "course_media",
    "user_uploads",
    "reports",
    "certificates",
}


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


class TestAllowOverwriteFileSystemStorage:
    """The local-disk stand-in for S3Storage's replace-at-an-existing-key
    behaviour. Stock FileSystemStorage suffixes instead, which is what left
    orphaned organisation logos behind."""

    def test_saving_over_an_existing_name_keeps_the_name(self, tmp_path) -> None:
        storage = FileSystemStorage(location=str(tmp_path), allow_overwrite=True)
        storage.save("logo.png", ContentFile(b"first"))

        name = storage.save("logo.png", ContentFile(b"second"))

        assert name == "logo.png"

    def test_saving_over_an_existing_name_replaces_the_bytes(self, tmp_path) -> None:
        storage = FileSystemStorage(location=str(tmp_path), allow_overwrite=True)
        storage.save("logo.png", ContentFile(b"first"))

        storage.save("logo.png", ContentFile(b"second"))

        assert (tmp_path / "logo.png").read_bytes() == b"second"
        assert sorted(path.name for path in tmp_path.iterdir()) == ["logo.png"]

    def test_a_free_name_is_used_unchanged(self, tmp_path) -> None:
        storage = FileSystemStorage(location=str(tmp_path), allow_overwrite=True)

        assert storage.save("logo.png", ContentFile(b"only")) == "logo.png"

    def test_asking_for_an_available_name_deletes_nothing(self, tmp_path) -> None:
        """get_available_name is a query, and has to stay one. Answering it by
        deleting first destroyed the old logo before the replacement was written,
        so a write that then failed left the organisation pointing at a key with
        nothing behind it."""
        storage = FileSystemStorage(location=str(tmp_path), allow_overwrite=True)
        storage.save("logo.png", ContentFile(b"first"))

        assert storage.get_available_name("logo.png") == "logo.png"
        assert (tmp_path / "logo.png").read_bytes() == b"first"

    def test_a_failed_write_leaves_the_key_in_place(self, tmp_path) -> None:
        """Overwriting truncates rather than unlinks, so a write that fails partway
        leaves an object at the key. The organisation row keeps pointing at
        something that exists, which is the difference that matters."""
        storage = FileSystemStorage(location=str(tmp_path), allow_overwrite=True)
        storage.save("logo.png", ContentFile(b"first"))

        class _FailingFile(ContentFile):
            def chunks(self, chunk_size: int | None = None) -> Iterator[bytes]:
                raise OSError("no space left on device")

        with pytest.raises(OSError, match="no space left on device"):
            storage.save("logo.png", _FailingFile(b"second"))

        assert storage.exists("logo.png")


def _options_of(entry: dict[str, object]) -> dict[str, object]:
    options = entry["OPTIONS"]
    assert isinstance(options, dict)
    return options


FILESYSTEM_ENTRY = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
OVERWRITING_FILESYSTEM_ENTRY = {
    "BACKEND": "django.core.files.storage.FileSystemStorage",
    "OPTIONS": {"allow_overwrite": True},
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
    set_env(monkeypatch, env)

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
    monkeypatch.setenv(
        "AWS_S3_SECRET_ACCESS_KEY", "shared-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("AWS_S3_ENDPOINT_URL", "https://shared.example.test")
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")
    monkeypatch.setenv(
        "AWS_S3_PUBLIC_SECRET_ACCESS_KEY", "public-only-secret"
    )  # pragma: allowlist secret
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
    monkeypatch.setenv(
        "AWS_S3_SECRET_ACCESS_KEY", "shared-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")
    monkeypatch.setenv(
        "AWS_S3_PUBLIC_SECRET_ACCESS_KEY", "public-only-secret"
    )  # pragma: allowlist secret

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["access_key"] == "public-only-key"
    assert options["secret_key"] == "public-only-secret"  # noqa: S105  # pragma: allowlist secret


@pytest.mark.parametrize(
    "alias", ["course_media", "user_uploads", "certificates", "reports", "default"]
)
def test_per_bucket_access_key_does_not_leak_to_other_aliases(
    alias: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv(
        "AWS_S3_SECRET_ACCESS_KEY", "shared-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("AWS_S3_PUBLIC_ACCESS_KEY_ID", "public-only-key")
    monkeypatch.setenv(
        "AWS_S3_PUBLIC_SECRET_ACCESS_KEY", "public-only-secret"
    )  # pragma: allowlist secret

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})[alias]
    )

    assert options["access_key"] == "shared-key"
    assert options["secret_key"] == "shared-secret"  # noqa: S105  # pragma: allowlist secret


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


# Case 12: an access key and its secret always come from the same source. A
# per-purpose key id paired with the shared secret signs every request with a
# key the secret does not match, and nothing downstream can see the mismatch.


def test_unset_per_purpose_credentials_take_both_halves_of_the_shared_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv(
        "AWS_S3_SECRET_ACCESS_KEY", "shared-secret"
    )  # pragma: allowlist secret

    options = _options_of(
        build_storages(staticfiles={"BACKEND": "some.backend"})["public"]
    )

    assert options["access_key"] == "shared-key"
    assert options["secret_key"] == "shared-secret"  # noqa: S105  # pragma: allowlist secret


def test_per_purpose_key_id_without_its_secret_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "shared-key")
    monkeypatch.setenv(
        "AWS_S3_SECRET_ACCESS_KEY", "shared-secret"
    )  # pragma: allowlist secret
    monkeypatch.setenv("AWS_S3_USER_UPLOADS_ACCESS_KEY_ID", "user-data-key")

    with pytest.raises(ImproperlyConfigured) as excinfo:
        build_storages(staticfiles={"BACKEND": "some.backend"})

    message = str(excinfo.value)
    assert "AWS_S3_USER_UPLOADS_ACCESS_KEY_ID" in message
    assert "AWS_S3_USER_UPLOADS_SECRET_ACCESS_KEY" in message


def test_per_purpose_secret_without_its_key_id_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv(
        "AWS_S3_USER_UPLOADS_SECRET_ACCESS_KEY", "user-data-secret"
    )  # pragma: allowlist secret

    with pytest.raises(ImproperlyConfigured) as excinfo:
        build_storages(staticfiles={"BACKEND": "some.backend"})

    message = str(excinfo.value)
    assert "AWS_S3_USER_UPLOADS_SECRET_ACCESS_KEY" in message
    assert "AWS_S3_USER_UPLOADS_ACCESS_KEY_ID" in message


# Case 13: which variable a bucket name came from. E003 needs to tell an alias
# that named its own bucket from one that inherited the shared name.


def test_bucket_name_for_reports_its_own_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")
    monkeypatch.setenv("AWS_S3_GENERATED_BUCKET_NAME", "fls-user-data")

    assert bucket_name_for("GENERATED") == ("fls-user-data", False)


def test_bucket_name_for_reports_the_shared_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    assert bucket_name_for("GENERATED") == ("fls-shared", True)


def test_bucket_name_for_reports_no_bucket_at_all() -> None:
    assert bucket_name_for("GENERATED") == (None, True)


# Case 14: the local-disk stand-in for the public alias overwrites through
# Django's own allow_overwrite rather than a subclass that deletes first.


def test_overwriting_filesystem_entry_uses_the_stock_backend() -> None:
    result = build_storages(staticfiles={"BACKEND": "some.backend"})

    assert result["public"]["BACKEND"] == FILESYSTEM_ENTRY["BACKEND"]
    assert _options_of(result["public"]) == {"allow_overwrite": True}


# Case 15: all three configurable alias names reach the emitted keys.


def test_custom_logo_and_content_media_aliases_emit_under_their_own_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "fls-shared")

    result = build_storages(
        staticfiles={"BACKEND": "some.backend"},
        logo_alias="branding",
        content_media_alias="courseware",
        reports_alias="generated_reports",
    )

    assert {"branding", "courseware", "generated_reports"} <= set(result)
    assert {"public", "course_media", "reports"}.isdisjoint(result)


def test_renamed_logo_alias_keeps_the_public_purpose_and_its_overwrite_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_S3_PUBLIC_BUCKET_NAME", "fls-prod-public")

    result = build_storages(
        staticfiles={"BACKEND": "some.backend"}, logo_alias="branding"
    )
    options = _options_of(result["branding"])

    assert options["bucket_name"] == "fls-prod-public"
    assert options["file_overwrite"] is True
    assert options["object_parameters"] == {"CacheControl": "public, max-age=86400"}
