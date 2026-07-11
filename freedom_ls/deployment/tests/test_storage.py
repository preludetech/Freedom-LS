from __future__ import annotations

from botocore.config import Config

from freedom_ls.deployment.storage import build_s3_media_storage


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
