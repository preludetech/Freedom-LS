"""Django system checks for the deployment app.

Check IDs follow Django's convention: ``app_label.severity + number``.
E = Error, W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``, except a check registered with ``deploy=True``, which runs
only under ``manage.py check --deploy``.

E001 — A media alias does not resolve to a bucket of its own: either it
       resolves where `default` resolves, so a misconfigured or missing
       per-bucket variable would serve learner uploads or reports out of the
       general-purpose default bucket, or it fell back to local disk under
       DEBUG=False. Runs only under ``manage.py check --deploy``.
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


@register(Tags.security, deploy=True)
def check_media_aliases_resolve_to_their_own_bucket(
    **kwargs: object,
) -> list[CheckMessage]:
    """E001: Error when a media alias does not resolve to a bucket of its own.

    Two ways that happens, and both are configuration errors:

    1. The alias resolves where 'default' resolves, because its per-bucket
       variable is missing and it fell through to the shared one.
    2. The alias resolves to local disk while 'default' does not. Nothing fell
       through, so a comparison against 'default' alone finds a difference and
       lets it past — but a misspelled per-bucket variable with no shared
       fallback lands the alias on the server's own disk, which is exactly the
       failure leaving the shared variable unset is meant to expose.

    Each media alias is compared against 'default' only, never against another
    media alias, so two media aliases sharing a bucket on purpose (public and
    certificates, say) is never flagged.

    Both arms are gated on DEBUG for the filesystem case: local disk is the
    normal dev and test configuration, and a staging environment may use it
    deliberately. Registered with deploy=True, so this only runs under
    `manage.py check --deploy` — a fresh checkout with no AWS_* variables set,
    where every alias falls through to 'default', never fails runserver,
    migrate, plain check, or the test suite.
    """
    from django.conf import settings

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
        if identity is None:
            continue
        if identity[0] == "fs" and settings.DEBUG:
            continue
        hint = f"Set AWS_S3_{purpose}_BUCKET_NAME to a bucket dedicated to {alias!r}."
        if identity == default_identity:
            errors.append(
                Error(
                    f"Storage alias {alias!r} resolves to the same bucket as "
                    f"'default'. Files meant for {alias!r} would be served "
                    f"from the general-purpose default bucket.",
                    hint=hint,
                    id="freedom_ls_deployment.E001",
                )
            )
        elif identity[0] == "fs":
            errors.append(
                Error(
                    f"Storage alias {alias!r} resolves to local filesystem "
                    f"storage while DEBUG is False. Files meant for {alias!r} "
                    f"would be written to the server's own disk instead of "
                    f"object storage, where they are neither backed up nor "
                    f"shared between instances.",
                    hint=hint,
                    id="freedom_ls_deployment.E001",
                )
            )
    return errors
