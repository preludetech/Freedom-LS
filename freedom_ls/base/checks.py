"""System checks for the base app.

E001 — HtmxMessagesMiddleware is not registered in MIDDLEWARE.
E002 — HtmxMessagesMiddleware is registered before MessageMiddleware.
E003 — VISITOR_COUNTRY_HEADER holds a request.META key instead of the header
       name itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import CheckMessage, Error, Tags, Warning, register

HTMX_MESSAGES_MIDDLEWARE = "freedom_ls.base.middleware.HtmxMessagesMiddleware"
DJANGO_MESSAGE_MIDDLEWARE = "django.contrib.messages.middleware.MessageMiddleware"


@register()
def check_htmx_messages_middleware(**kwargs: object) -> list[CheckMessage]:
    errors: list[CheckMessage] = []
    middleware: list[str] = list(settings.MIDDLEWARE)

    if HTMX_MESSAGES_MIDDLEWARE not in middleware:
        errors.append(
            Error(
                f"{HTMX_MESSAGES_MIDDLEWARE!r} is not registered in MIDDLEWARE.",
                hint=(
                    f"Add {HTMX_MESSAGES_MIDDLEWARE!r} to MIDDLEWARE, after "
                    f"{DJANGO_MESSAGE_MIDDLEWARE!r}."
                ),
                id="freedom_ls_base.E001",
            )
        )
        return errors

    if DJANGO_MESSAGE_MIDDLEWARE not in middleware:
        # Django's own checks will flag this; nothing for us to add.
        return errors

    if middleware.index(HTMX_MESSAGES_MIDDLEWARE) <= middleware.index(
        DJANGO_MESSAGE_MIDDLEWARE
    ):
        errors.append(
            Error(
                (
                    f"{HTMX_MESSAGES_MIDDLEWARE!r} must come after "
                    f"{DJANGO_MESSAGE_MIDDLEWARE!r} in MIDDLEWARE so the "
                    f"request-scoped message storage is attached before our "
                    f"middleware reads from it."
                ),
                id="freedom_ls_base.E002",
            )
        )

    return errors


def request_meta_key_error(
    *, setting_name: str, header_name: str | None, check_id: str, consequence: str
) -> list[Error]:
    """An Error when a header-name setting holds a request.META key (HTTP_...).

    A setting that names an HTTP header is read through request.headers,
    which never sees the request.META spelling, so a carried-over
    "HTTP_X_..." value silently never matches anything.
    """
    if not header_name or not header_name.startswith("HTTP_"):
        return []
    plain_name = header_name.removeprefix("HTTP_").replace("_", "-").title()
    return [
        Error(
            f"{setting_name} is {header_name!r}, which is a request.META key. "
            f"The setting names the HTTP header itself, so this value never "
            f"matches and {consequence}",
            hint=f"Use the header name instead, e.g. {plain_name!r}.",
            id=check_id,
        )
    ]


@register(Tags.security)
def check_visitor_country_header_is_not_a_meta_key(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[Error]:
    from freedom_ls.base.config import config

    return request_meta_key_error(
        setting_name="VISITOR_COUNTRY_HEADER",
        header_name=config.VISITOR_COUNTRY_HEADER,
        check_id="freedom_ls_base.E003",
        consequence="every visitor counts as unknown, so no ad pixel ever loads.",
    )


def pixel_without_visitor_country_warning(
    *, setting_name: str, pixel_id: str | None, check_id: str
) -> list[Warning]:
    """A W001 when a pixel ID is set but VISITOR_COUNTRY_HEADER is not.

    Every visitor counts as unknown without the header, so the pixel would
    never load for anyone.
    """
    from freedom_ls.base.config import config

    if not pixel_id or config.VISITOR_COUNTRY_HEADER:
        return []
    return [
        Warning(
            f"{setting_name} is set but VISITOR_COUNTRY_HEADER is not, so the "
            f"pixel would never load.",
            hint=(
                "Set VISITOR_COUNTRY_HEADER behind a proxy that sets it on "
                f"every request, or unset {setting_name}."
            ),
            id=check_id,
        )
    ]
