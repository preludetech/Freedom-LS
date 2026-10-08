"""Django system checks for the messaging policy app.

E001: MESSAGING_DEFAULT_FLAGS does not name exactly the flags, or holds a value
other than "open" or "closed".
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register

from freedom_ls.messaging_policy.config import config
from freedom_ls.messaging_policy.models import FLAG_NAMES, MessagingFlag

_RESOLVED_VALUES = (MessagingFlag.OPEN.value, MessagingFlag.CLOSED.value)


@register()
def check_default_flags(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    flags = config.MESSAGING_DEFAULT_FLAGS
    errors: list[CheckMessage] = []
    if set(flags) != set(FLAG_NAMES):
        errors.append(
            Error(
                f"MESSAGING_DEFAULT_FLAGS keys {sorted(flags)} must be exactly {sorted(FLAG_NAMES)}.",
                hint="Name every flag once and no others.",
                id="freedom_ls_messaging_policy.E001",
            )
        )
    bad_values = sorted(
        f"{name}={value!r}"
        for name, value in flags.items()
        if value not in _RESOLVED_VALUES
    )
    if bad_values:
        errors.append(
            Error(
                f"MESSAGING_DEFAULT_FLAGS has values other than 'open' or 'closed': {bad_values}.",
                hint="The settings layer must always decide, so 'inherit' is not allowed.",
                id="freedom_ls_messaging_policy.E001",
            )
        )
    return errors
