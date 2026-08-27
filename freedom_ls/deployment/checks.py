"""Django system checks for the deployment app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``, except a check registered with ``deploy=True``, which runs
only under ``manage.py check --deploy``.

E001 — A media alias resolves where `default` resolves, so a misconfigured or
       missing per-bucket variable would serve learner uploads or reports out
       of the general-purpose default bucket. Runs only under
       ``manage.py check --deploy``.
E002 — A media alias resolves to local filesystem storage while DEBUG is
       False, so learner data would be written to the server's own disk. A
       separate id from E001 on purpose: a deployment that serves media from
       local disk deliberately can silence this without also giving up E001's
       bucket-collision protection. Runs only under
       ``manage.py check --deploy``.
E003 — A media alias took its bucket from the shared AWS_STORAGE_BUCKET_NAME
       because its own per-bucket variable is unset, so several aliases share
       one bucket without any of them matching `default`. Runs only under
       ``manage.py check --deploy``.
E004 — A media alias that must serve signed URLs resolves with querystring
       auth off, so its objects would be reachable by anyone holding the URL.
       Runs only under ``manage.py check --deploy``.
W001 — SENTRY_DSN is set but SENTRY_RELEASE is blank, so Sentry events would
       ship untagged.
"""

from __future__ import annotations

from collections.abc import Sequence

from storages.backends.s3 import S3Storage

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, Tags, Warning, register
from django.core.files.storage import (
    FileSystemStorage,
    InvalidStorageError,
    Storage,
    storages,
)


@register()
def check_sentry_release_set_when_dsn_set(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Warning]:
    """W001: warn when SENTRY_DSN is set but SENTRY_RELEASE is blank/unset.

    A blank release only degrades Sentry's release-based features; it never
    breaks the running app — hence a Warning, not an Error. Silenceable via
    SILENCED_SYSTEM_CHECKS ("freedom_ls_deployment.W001").
    """
    from freedom_ls.deployment.config import config

    if not config.SENTRY_DSN:
        return []
    if config.SENTRY_RELEASE:
        return []
    return [
        Warning(
            "SENTRY_DSN is set but SENTRY_RELEASE is blank — Sentry events will "
            "be untagged, so regressions cannot be tied to a deploy.",
            hint=(
                "Set SENTRY_RELEASE (e.g. the git SHA) in this environment, or "
                "silence freedom_ls_deployment.W001 if release tracking is "
                "intentionally disabled."
            ),
            id="freedom_ls_deployment.W001",
        )
    ]


def _configured_media_aliases() -> dict[str, str]:
    """Every media alias under the name its app's *_STORAGE_ALIAS setting gives it.

    Three of the five names are settings, so nothing here may hardcode them: a
    project that renamed one would otherwise be checked on keys that do not exist
    while the keys that do go unchecked.
    """
    from freedom_ls.content_engine.config import config as content_config
    from freedom_ls.deployment.storage import media_alias_purposes
    from freedom_ls.organisations.config import config as organisations_config
    from freedom_ls.reports.config import config as reports_config

    return media_alias_purposes(
        logo_alias=organisations_config.ORGANISATION_LOGO_STORAGE_ALIAS,
        content_media_alias=content_config.CONTENT_MEDIA_STORAGE_ALIAS,
        reports_alias=reports_config.REPORTS_STORAGE_ALIAS,
    )


def _storage_identity(storage: Storage) -> tuple[str | None, ...] | None:
    """Where a Storage writes, or None when the backend cannot be compared safely.

    An unrecognised backend returns None rather than raising, so a downstream
    project's custom Storage subclass never becomes a false positive that gets
    the whole check silenced.
    """
    if isinstance(storage, S3Storage):
        return ("s3", storage.bucket_name, storage.endpoint_url)
    if isinstance(storage, FileSystemStorage):
        return ("fs", str(storage.location))
    return None


def _bucket_hint(alias: str, purpose: str) -> str:
    """The one-line fix for an alias that is not on a bucket of its own."""
    return f"Set AWS_S3_{purpose}_BUCKET_NAME to a bucket dedicated to {alias!r}."


@register(Tags.security, deploy=True)
def check_media_aliases_not_shared_with_default(
    **kwargs: object,
) -> list[CheckMessage]:
    """E001: Error when a media alias resolves where 'default' resolves.

    That happens when the alias's per-bucket variable is missing and it fell
    through to the shared one, with 'default' having fallen through too. Each
    media alias is compared against 'default' only, never against another media
    alias, so two media aliases sharing a bucket on purpose (public and
    certificates, say) is never flagged. When 'default' names a bucket of its own
    the comparison sees nothing, which is what E003 is for.

    An alias on local disk is skipped here whatever 'default' points at: that
    whole class belongs to E002, which reports it once rather than leaving one
    misconfiguration to produce two errors.

    The undeclared-alias branch reaches only an alias no model field binds. A
    bound `storage=` callable is resolved at class definition, so an undeclared
    alias raises InvalidStorageError while Django imports the model, long before
    any check runs.

    Registered with deploy=True, so this only runs under `manage.py check
    --deploy` — a fresh checkout with no AWS_* variables set, where every alias
    falls through to 'default', never fails runserver, migrate, plain check, or
    the test suite.
    """
    try:
        default_identity = _storage_identity(storages["default"])
    except InvalidStorageError:
        return [
            Error(
                "settings.STORAGES declares no 'default' key.",
                hint="Declare a 'default' entry in settings.STORAGES.",
                id="freedom_ls_deployment.E001",
            )
        ]
    if default_identity is None:
        return []

    errors: list[CheckMessage] = []
    for alias, purpose in _configured_media_aliases().items():
        try:
            identity = _storage_identity(storages[alias])
        except InvalidStorageError:
            errors.append(
                Error(
                    f"Storage alias {alias!r} is not declared in settings.STORAGES.",
                    hint=f"Declare {alias!r} in settings.STORAGES.",
                    id="freedom_ls_deployment.E001",
                )
            )
            continue
        if identity is None or identity[0] == "fs":
            continue
        if identity == default_identity:
            errors.append(
                Error(
                    f"Storage alias {alias!r} resolves to the same bucket as "
                    f"'default'. Files meant for {alias!r} would be served "
                    f"from the general-purpose default bucket.",
                    hint=_bucket_hint(alias, purpose),
                    id="freedom_ls_deployment.E001",
                )
            )
    return errors


@register(Tags.security, deploy=True)
def check_media_aliases_not_on_local_disk(
    **kwargs: object,
) -> list[CheckMessage]:
    """E002: Error when a media alias resolves to local disk outside DEBUG.

    E001 compares each alias against 'default' and so cannot see this one: with
    AWS_S3_DEFAULT_BUCKET_NAME set to its own bucket, as the production
    configuration requires, a misspelled per-bucket variable drops that alias
    to FileSystemStorage while 'default' stays on S3. The two identities differ,
    E001 finds nothing, and cohort report PDFs naming learners land on the
    container's disk.

    Gated on DEBUG, because local disk is the normal development and test
    configuration. An undeclared alias is skipped rather than reported: E001
    already names it, and one missing key should not produce two errors.
    """
    from django.conf import settings

    if settings.DEBUG:
        return []

    errors: list[CheckMessage] = []
    for alias, purpose in _configured_media_aliases().items():
        try:
            identity = _storage_identity(storages[alias])
        except InvalidStorageError:
            continue
        if identity is None or identity[0] != "fs":
            continue
        errors.append(
            Error(
                f"Storage alias {alias!r} resolves to local filesystem storage "
                f"while DEBUG is False. Files meant for {alias!r} would be "
                f"written to the server's own disk instead of object storage, "
                f"where they are neither backed up nor shared between instances.",
                hint=_bucket_hint(alias, purpose),
                id="freedom_ls_deployment.E002",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_media_aliases_name_their_own_bucket(
    **kwargs: object,
) -> list[CheckMessage]:
    """E003: Error when a media alias inherited the shared bucket name.

    E001's comparison against 'default' works only while 'default' holds a bucket
    name nothing else uses. Leave a legacy AWS_STORAGE_BUCKET_NAME set alongside
    a distinct AWS_S3_DEFAULT_BUCKET_NAME — a configuration this code supports and
    the deployment checklist documents — and misspell one per-bucket variable, and
    that alias lands in whatever the shared name points at. The identities differ,
    so E001 stays silent; the alias is on S3, so E002 skips it; and report PDFs
    naming learners can end up in the anonymously readable bucket with a clean
    `check --deploy`.

    Both halves of the test have to hold: the per-bucket variable unset, and the
    alias actually resolving to the value the shared variable holds. That is what
    keeps a project building its own STORAGES dict out of the way.
    """
    from freedom_ls.deployment.storage import bucket_name_for

    errors: list[CheckMessage] = []
    for alias, purpose in _configured_media_aliases().items():
        bucket, from_shared = bucket_name_for(purpose)
        if not bucket or not from_shared:
            continue
        try:
            identity = _storage_identity(storages[alias])
        except InvalidStorageError:
            continue
        if identity is None or identity[0] != "s3" or identity[1] != bucket:
            continue
        errors.append(
            Error(
                f"Storage alias {alias!r} took its bucket {bucket!r} from the "
                f"shared AWS_STORAGE_BUCKET_NAME, because "
                f"AWS_S3_{purpose}_BUCKET_NAME is not set. Every alias missing "
                f"its own variable lands in that one bucket together.",
                hint=(
                    f"{_bucket_hint(alias, purpose)} Leave AWS_STORAGE_BUCKET_NAME "
                    f"unset in production, so a misspelled per-bucket variable "
                    f"fails loudly instead of falling through."
                ),
                id="freedom_ls_deployment.E003",
            )
        )
    return errors


@register(Tags.security, deploy=True)
def check_private_media_aliases_sign_their_urls(
    **kwargs: object,
) -> list[CheckMessage]:
    """E004: Error when an alias holding private files serves unsigned URLs.

    AWS_QUERYSTRING_AUTH in its shared form reaches every media alias, and a
    project that opted into public media under the single-bucket layout carries
    it forward through the upgrade. Course media, user uploads and cohort reports
    would then be readable by anyone holding the URL — permanently, since an
    unsigned URL never expires.

    Only S3-backed aliases are considered. Local disk has no signing to lose, and
    E002 already owns that whole class.
    """
    from freedom_ls.deployment.storage import SIGNED_URL_PURPOSES

    errors: list[CheckMessage] = []
    for alias, purpose in _configured_media_aliases().items():
        if purpose not in SIGNED_URL_PURPOSES:
            continue
        try:
            storage = storages[alias]
        except InvalidStorageError:
            continue
        if not isinstance(storage, S3Storage) or storage.querystring_auth:
            continue
        errors.append(
            Error(
                f"Storage alias {alias!r} resolves with querystring auth off, so "
                f"its URLs are unsigned and never expire. Files meant for "
                f"{alias!r} would be readable by anyone who is handed one.",
                hint=(
                    f"Leave AWS_QUERYSTRING_AUTH unset, or set it to True — its "
                    f"shared form reaches every media alias. Set "
                    f"AWS_S3_{purpose}_QUERYSTRING_AUTH only if {alias!r} really "
                    f"is meant to be anonymously readable."
                ),
                id="freedom_ls_deployment.E004",
            )
        )
    return errors
