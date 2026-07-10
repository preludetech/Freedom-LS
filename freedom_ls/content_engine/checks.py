"""Django system checks for the content_engine app.

E001 — A required setting the project must supply is unset. Currently only
       ADMONITION_TYPES, which has no safe default (the consumer reads
       registry["default"], so an unset registry would KeyError at render time).
"""

from __future__ import annotations

from django.core.checks import CheckMessage, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_content_engine_settings(**kwargs: object) -> list[CheckMessage]:
    """E001: Report any required content_engine setting the project has not set."""
    from freedom_ls.content_engine.config import config

    return required_settings_errors(config, "freedom_ls_content_engine")
