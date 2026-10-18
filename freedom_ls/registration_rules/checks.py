"""Django system checks for the registration_rules app.

E001 - hr_attributes is not installed.
E002 - A REGISTRATION_RULE_KINDS path does not import.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.apps import AppConfig
from django.core.checks import CheckMessage, Error, register
from django.utils.module_loading import import_string


@register()
def check_hr_attributes_installed(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E001: rules read the lists and the switch that hr_attributes owns."""
    from django.apps import apps

    if apps.is_installed("freedom_ls.hr_attributes"):
        return []
    return [
        Error(
            "freedom_ls.registration_rules requires freedom_ls.hr_attributes.",
            hint='Add "freedom_ls.hr_attributes" to INSTALLED_APPS before "freedom_ls.registration_rules".',
            id="freedom_ls_registration_rules.E001",
        )
    ]


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
