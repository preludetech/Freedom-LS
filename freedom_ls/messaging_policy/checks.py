"""Django system checks for the messaging policy app.

E001: MESSAGING_DEFAULT_FLAGS does not name exactly the flags, or holds a value
other than "open" or "closed".
E002: MESSAGING_OFFERED_EDUCATOR_ROLES names a role the base role config or a
site's role config does not define.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register

from freedom_ls.messaging_policy.config import config
from freedom_ls.messaging_policy.models import FLAG_NAMES, MessagingFlag
from freedom_ls.role_based_permissions.config import (
    config as role_permissions_config,
)
from freedom_ls.role_based_permissions.loader import (
    get_role_config,
    load_base_config,
)

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


@register()
def check_offered_roles_exist(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    site_names = sorted(role_permissions_config.FREEDOMLS_PERMISSIONS_MODULES)
    role_configs = {
        "the base role config": load_base_config(),
        **{
            f"the role config of site {name!r}": get_role_config(name)
            for name in site_names
        },
    }
    errors: list[CheckMessage] = []
    for role in config.MESSAGING_OFFERED_EDUCATOR_ROLES:
        missing_from = [
            label
            for label, role_config in role_configs.items()
            if role not in role_config
        ]
        if missing_from:
            errors.append(
                Error(
                    f"MESSAGING_OFFERED_EDUCATOR_ROLES names {role!r}, which is not in {', '.join(missing_from)}.",
                    hint="Offer only roles that every role config defines.",
                    id="freedom_ls_messaging_policy.E002",
                )
            )
    return errors
