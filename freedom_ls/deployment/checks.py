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
    through to the shared one. Each media alias is compared against 'default'
    only, never against another media alias, so two media aliases sharing a
    bucket on purpose (public and certificates, say) is never flagged.

    An alias on local disk is skipped here whatever 'default' points at: that
    whole class belongs to E002, which reports it once rather than leaving one
    misconfiguration to produce two errors.

    Registered with deploy=True, so this only runs under `manage.py check
    --deploy` — a fresh checkout with no AWS_* variables set, where every alias
    falls through to 'default', never fails runserver, migrate, plain check, or
    the test suite.
    """
    from freedom_ls.deployment.storage import media_alias_purposes
    from freedom_ls.reports.config import config as reports_config

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
    for alias, purpose in media_alias_purposes(
        reports_config.REPORTS_STORAGE_ALIAS
    ).items():
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

    from freedom_ls.deployment.storage import media_alias_purposes
    from freedom_ls.reports.config import config as reports_config

    if settings.DEBUG:
        return []

    errors: list[CheckMessage] = []
    for alias, purpose in media_alias_purposes(
        reports_config.REPORTS_STORAGE_ALIAS
    ).items():
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
