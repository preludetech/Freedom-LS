from __future__ import annotations

from botocore.config import Config


def build_s3_media_storage(
    *,
    bucket_name: str,
    access_key: str | None,
    secret_key: str | None,
    endpoint_url: str | None,
    region_name: str | None,
    custom_domain: str | None,
    querystring_auth: bool,
    querystring_expire: int,
) -> dict[str, object]:
    """Assemble the STORAGES['default'] entry for an R2 (S3-compatible) bucket.

    R2 landmines handled here: no ACLs (R2 has none), the boto3 >=1.35.99 checksum
    headers R2 rejects, and region defaulting to "auto".
    """
    options: dict[str, object] = {
        "bucket_name": bucket_name,
        "access_key": access_key,
        "secret_key": secret_key,
        "endpoint_url": endpoint_url,
        "region_name": region_name or "auto",
        "signature_version": "s3v4",
        "querystring_auth": querystring_auth,
        "querystring_expire": querystring_expire,
        "client_config": Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }
    if custom_domain:
        options["custom_domain"] = custom_domain
    return {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": options}
