"""Django system checks for the organisations app.

E001 — A required organisations setting the project must supply is unset.
       Currently none of the settings this app declares are required, so this
       returns nothing today; it costs one line and keeps the app honest if a
       required setting is added later.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_organisations_settings(**kwargs: object) -> list[CheckMessage]:
    """E001: Report any required organisations setting the project has not set."""
    from freedom_ls.organisations.config import config

    return required_settings_errors(config, "freedom_ls_organisations")
