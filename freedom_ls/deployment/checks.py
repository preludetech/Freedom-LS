"""Django system checks for the deployment app.

Check IDs follow Django's convention: ``app_label.severity + number``.
W = Warning. Checks run automatically on runserver, migrate, test, and
``manage.py check``.

W001 — SENTRY_DSN is set but SENTRY_RELEASE is blank, so Sentry events would
       ship untagged.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import Warning, register


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
