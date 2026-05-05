"""System checks for the base app.

E001 — HtmxMessagesMiddleware is not registered in MIDDLEWARE.
E002 — HtmxMessagesMiddleware is registered before MessageMiddleware.
"""

from __future__ import annotations

from django.conf import settings
from django.core.checks import CheckMessage, Error, register

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
