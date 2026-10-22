"""Django system checks for the registration_rules app.

E002 - A REGISTRATION_RULE_KINDS path does not import.
E003 - The kind a new rule gets by default is not in REGISTRATION_RULE_KINDS.

A missing hr_attributes is refused by the app config instead (E001 is retired):
the app cannot load far enough without it for a check to run.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register
from django.utils.module_loading import import_string


@register()
def check_rule_kinds_import(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E002: every REGISTRATION_RULE_KINDS path must import, or a rule of that kind can never run."""
    from freedom_ls.registration_rules.config import config

    errors: list[CheckMessage] = []
    for key, dotted in config.REGISTRATION_RULE_KINDS.items():
        try:
            import_string(dotted)
        except ImportError as exc:
            errors.append(
                Error(
                    f"REGISTRATION_RULE_KINDS[{key!r}] = {dotted!r} does not import: {exc}",
                    id="freedom_ls_registration_rules.E002",
                )
            )
    return errors


@register()
def check_default_kind_is_configured(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E003: the model's default kind must be a configured kind, or every new rule is unloadable."""
    from freedom_ls.registration_rules.config import config
    from freedom_ls.registration_rules.models import RegistrationRule

    default = RegistrationRule._meta.get_field("kind").default
    if default in config.REGISTRATION_RULE_KINDS:
        return []
    return [
        Error(
            f"REGISTRATION_RULE_KINDS has no {default!r} entry, the kind every new rule gets.",
            hint="Add it, or change RegistrationRule.kind's default in a project model.",
            id="freedom_ls_registration_rules.E003",
        )
    ]
