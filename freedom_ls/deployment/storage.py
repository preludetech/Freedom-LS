from __future__ import annotations

from urllib.parse import urlsplit

from botocore.config import Config

from django.core.exceptions import ImproperlyConfigured

from freedom_ls.base.env import env_bool, env_int, env_str, first_set_name

LOGO_PURPOSE = "PUBLIC"
CONTENT_MEDIA_PURPOSE = "COURSE_MEDIA"
USER_UPLOADS_PURPOSE = "USER_UPLOADS"
CERTIFICATES_PURPOSE = "CERTIFICATES"
PROFILE_PICTURES_PURPOSE = "PROFILE_PICTURES"
REPORTS_PURPOSE = "GENERATED"
DEFAULT_PURPOSE = "DEFAULT"

#: The media aliases whose name is fixed, because no setting names them:
#: user_uploads holds QuestionAnswerFile.file, profile_pictures holds
#: User.profile_picture, and certificates has no consumer yet. The other three
#: are named by ORGANISATION_LOGO_STORAGE_ALIAS, CONTENT_MEDIA_STORAGE_ALIAS and
#: REPORTS_STORAGE_ALIAS, so they arrive as arguments rather than as constants
#: here.
FIXED_ALIAS_PURPOSES: dict[str, str] = {
    "user_uploads": USER_UPLOADS_PURPOSE,
    "certificates": CERTIFICATES_PURPOSE,
    "profile_pictures": PROFILE_PICTURES_PURPOSE,
}

#: Purposes whose objects must never be reachable without a signature. Keyed by
#: purpose rather than by alias, as everything below is, because three of the six
#: alias names are settings a downstream project can change.
SIGNED_URL_PURPOSES: frozenset[str] = frozenset(
    {
        CONTENT_MEDIA_PURPOSE,
        USER_UPLOADS_PURPOSE,
        REPORTS_PURPOSE,
        PROFILE_PICTURES_PURPOSE,
    }
)

_OBJECT_PARAMETERS: dict[str, dict[str, str]] = {
    LOGO_PURPOSE: {"CacheControl": "public, max-age=86400"},
    CERTIFICATES_PURPOSE: {"CacheControl": "public, max-age=31536000, immutable"},
}

#: Purposes whose upload_to returns a stable key and whose object is meant to
#: change at that key. The logo purpose holds Organisation.logo at
#: organisations/{pk}{ext}, so replacing a logo has to replace that object —
#: which is also why it gets max-age=86400 rather than an immutable header.
#: CERTIFICATES is deliberately absent: a uuid-keyed certificate is written once
#: and must never be clobbered.
_OVERWRITE_PURPOSES: frozenset[str] = frozenset({LOGO_PURPOSE})

_FILE_SYSTEM_BACKEND = "django.core.files.storage.FileSystemStorage"


def media_alias_purposes(
    *,
    logo_alias: str = "public",
    content_media_alias: str = "course_media",
    reports_alias: str = "reports",
) -> dict[str, str]:
    """The six media aliases and their purposes, each under its configured name.

    The defaults match the declared defaults of the three settings that name these
    aliases, so a caller with no opinion gets the standard layout.
    """
    return {
        logo_alias: LOGO_PURPOSE,
        content_media_alias: CONTENT_MEDIA_PURPOSE,
        reports_alias: REPORTS_PURPOSE,
        **FIXED_ALIAS_PURPOSES,
    }


def bucket_name_for(purpose: str) -> tuple[str | None, bool]:
    """The bucket for ``purpose``, and whether it came from the shared variable.

    The flag is what lets a check tell an alias that named its own bucket from one
    that inherited whatever AWS_STORAGE_BUCKET_NAME happens to hold.
    """
    own = env_str(f"AWS_S3_{purpose}_BUCKET_NAME")
    if own:
        return own, False
    return env_str("AWS_STORAGE_BUCKET_NAME"), True


def _credential_pair(purpose: str) -> tuple[str | None, str | None]:
    """The access key and its secret for ``purpose``, always from one source.

    Resolving the two halves independently let a per-purpose key id pair with the
    shared secret, which signs every request with a key the secret does not match
    and surfaces only as SignatureDoesNotMatch on the first write. A half-set pair
    is never intentional, so it raises rather than falling back silently.
    """
    key_name = f"AWS_S3_{purpose}_ACCESS_KEY_ID"
    secret_name = f"AWS_S3_{purpose}_SECRET_ACCESS_KEY"
    key, secret = env_str(key_name), env_str(secret_name)
    if key and secret:
        return key, secret
    if key or secret:
        set_name, missing_name = (
            (key_name, secret_name) if key else (secret_name, key_name)
        )
        raise ImproperlyConfigured(
            f"{set_name} is set but {missing_name} is not. Set both, or neither — "
            f"neither falls back to AWS_S3_ACCESS_KEY_ID and "
            f"AWS_S3_SECRET_ACCESS_KEY."
        )
    return env_str("AWS_S3_ACCESS_KEY_ID"), env_str("AWS_S3_SECRET_ACCESS_KEY")


def _property_name(purpose: str, prop: str, shared: str) -> str:
    """The environment variable that sets `prop` for `purpose`.

    The purpose's own variable when it is set, otherwise the shared one.
    """
    return first_set_name(f"AWS_S3_{purpose}_{prop}", shared) or shared


def media_csp_sources(purpose: str) -> list[str]:
    """The origins a browser loads `purpose`'s objects from; empty on local disk.

    Reads the same custom domain or endpoint `_alias_entry` hands the storage,
    so the policy and the URLs the storage mints cannot name different hosts.
    """
    bucket, _from_shared = bucket_name_for(purpose)
    if not bucket:
        return []
    custom_domain = env_str(
        _property_name(purpose, "CUSTOM_DOMAIN", "AWS_S3_CUSTOM_DOMAIN")
    )
    if custom_domain:
        return [f"https://{custom_domain}"]
    endpoint = env_str(_property_name(purpose, "ENDPOINT_URL", "AWS_S3_ENDPOINT_URL"))
    if not endpoint:
        return []
    host = urlsplit(endpoint).netloc
    # A signed URL puts the bucket in the path or in a subdomain of the
    # endpoint, depending on the addressing style the client picks. The
    # subdomain is named, never wildcarded: a wildcard would allow every
    # other bucket on a shared endpoint host.
    return [f"https://{host}", f"https://{bucket}.{host}"]


def _alias_entry(purpose: str) -> dict[str, object]:
    """One STORAGES entry, resolved from the purpose's own environment variables.

    Falls back to the shared AWS_* variables, then to FileSystemStorage when
    neither names a bucket.
    """
    overwrite = purpose in _OVERWRITE_PURPOSES
    bucket, _from_shared = bucket_name_for(purpose)
    if not bucket:
        entry: dict[str, object] = {"BACKEND": _FILE_SYSTEM_BACKEND}
        if overwrite:
            entry["OPTIONS"] = {"allow_overwrite": True}
        return entry

    access_key, secret_key = _credential_pair(purpose)
    return build_s3_media_storage(
        bucket_name=bucket,
        access_key=access_key,
        secret_key=secret_key,
        endpoint_url=env_str(
            _property_name(purpose, "ENDPOINT_URL", "AWS_S3_ENDPOINT_URL")
        ),
        region_name=env_str(
            _property_name(purpose, "REGION_NAME", "AWS_S3_REGION_NAME")
        ),
        custom_domain=env_str(
            _property_name(purpose, "CUSTOM_DOMAIN", "AWS_S3_CUSTOM_DOMAIN")
        ),
        querystring_auth=env_bool(
            _property_name(purpose, "QUERYSTRING_AUTH", "AWS_QUERYSTRING_AUTH"), True
        ),
        querystring_expire=env_int(
            _property_name(purpose, "QUERYSTRING_EXPIRE", "AWS_QUERYSTRING_EXPIRE"),
            3600,
        ),
        object_parameters=_OBJECT_PARAMETERS.get(purpose),
        file_overwrite=overwrite,
    )


def build_storages(
    *,
    staticfiles: dict[str, object],
    logo_alias: str = "public",
    content_media_alias: str = "course_media",
    reports_alias: str = "reports",
) -> dict[str, dict[str, object]]:
    """Every STORAGES key, each alias resolved from its own environment variables.

    The three alias names are arguments rather than constants so that the settings
    naming them and the keys emitted here cannot drift apart: a project that renamed
    an alias without the key following crashed at model import.
    """
    storages: dict[str, dict[str, object]] = {
        alias: _alias_entry(purpose)
        for alias, purpose in media_alias_purposes(
            logo_alias=logo_alias,
            content_media_alias=content_media_alias,
            reports_alias=reports_alias,
        ).items()
    }
    storages["default"] = _alias_entry(DEFAULT_PURPOSE)
    storages["staticfiles"] = staticfiles
    return storages


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
    object_parameters: dict[str, str] | None = None,
    file_overwrite: bool = False,
) -> dict[str, object]:
    """Assemble a single STORAGES alias entry for an R2 (S3-compatible) bucket.

    R2 landmines handled here: no ACLs (R2 has none), the boto3 >=1.35.99 checksum
    headers R2 rejects, and region defaulting to "auto". `file_overwrite` is always
    written rather than left to the django-storages default, because whether a
    write at an existing key replaces or renames is a decision each alias makes.
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
        "file_overwrite": file_overwrite,
        "client_config": Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }
    if custom_domain:
        options["custom_domain"] = custom_domain
    if object_parameters:
        options["object_parameters"] = object_parameters
    return {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": options}
