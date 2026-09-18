"""Django system checks for the content_engine app.

E001 — A required setting the project must supply is unset. Currently only
       ADMONITION_TYPES, which has no safe default (the consumer reads
       registry["default"], so an unset registry would KeyError at render time).
E002 — DEFAULT_CURRENCY is set to a value Babel does not recognise as an ISO
       4217 currency code.
E003 — PRICE_LOCALE is set to a value Babel cannot parse as a locale.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error, register

from freedom_ls.base.app_settings import required_settings_errors


@register()
def check_required_content_engine_settings(**kwargs: object) -> list[CheckMessage]:
    """E001: Report any required content_engine setting the project has not set."""
    from freedom_ls.content_engine.config import config

    return required_settings_errors(config, "freedom_ls_content_engine")


@register()
def check_price_settings(**kwargs: object) -> list[CheckMessage]:
    """E002/E003: Report a DEFAULT_CURRENCY or PRICE_LOCALE Babel does not recognise."""
    from babel import Locale, UnknownLocaleError
    from babel.numbers import list_currencies

    from freedom_ls.content_engine.config import config

    errors: list[CheckMessage] = []
    if (
        config.DEFAULT_CURRENCY is not None
        and config.DEFAULT_CURRENCY not in list_currencies()
    ):
        errors.append(
            Error(
                f"DEFAULT_CURRENCY {config.DEFAULT_CURRENCY!r} is not a currency Babel recognises.",
                hint="Set DEFAULT_CURRENCY to an ISO 4217 code, e.g. 'ZAR'.",
                id="freedom_ls_content_engine.E002",
            )
        )
    if config.PRICE_LOCALE is not None:
        try:
            Locale.parse(config.PRICE_LOCALE)
        except (UnknownLocaleError, ValueError):
            errors.append(
                Error(
                    f"PRICE_LOCALE {config.PRICE_LOCALE!r} is not a locale Babel recognises.",
                    hint="Set PRICE_LOCALE to a Babel locale, e.g. 'en_ZA'.",
                    id="freedom_ls_content_engine.E003",
                )
            )
    return errors
