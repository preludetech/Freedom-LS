from __future__ import annotations

from botocore.config import Config

from django.core.files.storage import FileSystemStorage

from freedom_ls.base.env import env_bool, env_int, env_str, first_set_name

#: The media aliases whose name is fixed. `reports` is absent because its alias
#: name is configurable, and `default` because it is not a media alias.
MEDIA_ALIAS_PURPOSES: dict[str, str] = {
    "public": "PUBLIC",
    "course_media": "COURSE_MEDIA",
    "user_uploads": "USER_UPLOADS",
    "certificates": "CERTIFICATES",
}

#: The purpose prefix behind whatever REPORTS_STORAGE_ALIAS resolves to.
REPORTS_PURPOSE = "GENERATED"

DEFAULT_PURPOSE = "DEFAULT"

_OBJECT_PARAMETERS: dict[str, dict[str, str]] = {
    "public": {"CacheControl": "public, max-age=86400"},
    "certificates": {"CacheControl": "public, max-age=31536000, immutable"},
}

#: Aliases whose upload_to returns a stable key and whose object is meant to
#: change at that key. `public` holds Organisation.logo at
#: organisations/{pk}{ext}, so replacing a logo has to replace that object —
#: which is also why this alias gets max-age=86400 rather than an immutable
#: header. `certificates` is deliberately absent: a uuid-keyed certificate is
#: written once and must never be clobbered.
_OVERWRITE_ALIASES: frozenset[str] = frozenset({"public"})

_FILE_SYSTEM_BACKEND = "django.core.files.storage.FileSystemStorage"
_OVERWRITING_FILE_SYSTEM_BACKEND = (
    "freedom_ls.deployment.storage.OverwritingFileSystemStorage"
)


class OverwritingFileSystemStorage(FileSystemStorage):
    """Replaces the file at an existing name instead of suffixing a new one.

    S3Storage replaces the object at an existing key; FileSystemStorage appends
    a random suffix. An alias whose keys are stable needs the S3 behaviour in
    development and test too, or a replaced organisation logo lands at a new key
    locally and at the old one in production.
    """

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self.exists(name):
            self.delete(name)
        return super().get_available_name(name, max_length=max_length)


def media_alias_purposes(reports_alias: str) -> dict[str, str]:
    """The five media aliases and their purposes, reports under its own alias name."""
    return {**MEDIA_ALIAS_PURPOSES, reports_alias: REPORTS_PURPOSE}


def _alias_entry(alias: str, purpose: str) -> dict[str, object]:
    """One STORAGES entry, resolved from the purpose's own environment variables.

    Falls back to the shared AWS_* variables, then to FileSystemStorage when
    neither names a bucket.
    """
    overwrite = alias in _OVERWRITE_ALIASES
    bucket = env_str(f"AWS_S3_{purpose}_BUCKET_NAME") or env_str(
        "AWS_STORAGE_BUCKET_NAME"
    )
    if not bucket:
        return {
            "BACKEND": _OVERWRITING_FILE_SYSTEM_BACKEND
            if overwrite
            else _FILE_SYSTEM_BACKEND
        }

    def name_for(prop: str, shared: str) -> str:
        return first_set_name(f"AWS_S3_{purpose}_{prop}", shared) or shared

    return build_s3_media_storage(
        bucket_name=bucket,
        access_key=env_str(name_for("ACCESS_KEY_ID", "AWS_S3_ACCESS_KEY_ID")),
        secret_key=env_str(name_for("SECRET_ACCESS_KEY", "AWS_S3_SECRET_ACCESS_KEY")),
        endpoint_url=env_str(name_for("ENDPOINT_URL", "AWS_S3_ENDPOINT_URL")),
        region_name=env_str(name_for("REGION_NAME", "AWS_S3_REGION_NAME")),
        custom_domain=env_str(name_for("CUSTOM_DOMAIN", "AWS_S3_CUSTOM_DOMAIN")),
        querystring_auth=env_bool(
            name_for("QUERYSTRING_AUTH", "AWS_QUERYSTRING_AUTH"), True
        ),
        querystring_expire=env_int(
            name_for("QUERYSTRING_EXPIRE", "AWS_QUERYSTRING_EXPIRE"), 3600
        ),
        object_parameters=_OBJECT_PARAMETERS.get(alias),
        file_overwrite=overwrite,
    )


def build_storages(
    *,
    staticfiles: dict[str, object],
    reports_alias: str = "reports",
) -> dict[str, dict[str, object]]:
    """Every STORAGES key, each alias resolved from its own environment variables."""
    storages: dict[str, dict[str, object]] = {
        alias: _alias_entry(alias, purpose)
        for alias, purpose in media_alias_purposes(reports_alias).items()
    }
    storages["default"] = _alias_entry("default", DEFAULT_PURPOSE)
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
