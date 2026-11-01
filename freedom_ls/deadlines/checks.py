"""Django system checks for the deadlines app.

E001: DEADLINE_POLICY_DEFAULTS does not name exactly the six settings, or holds a value of
the wrong type or outside its choices. The settings layer must always decide, so "inherit"
and None are not allowed.
E002: DEADLINE_POLICY does not import, is not a DeadlinePolicy subclass, or names an FLS
app that is not installed.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from django.apps import AppConfig, apps
from django.core.checks import CheckMessage, Error, register
from django.utils.module_loading import import_string

from freedom_ls.deadlines.config import config
from freedom_ls.deadlines.models import (
    CONFIG_FIELDS,
    SWITCH_FIELDS,
    AfterAccessEnded,
)
from freedom_ls.deadlines.policy import DeadlinePolicy

_RESOLVED_AFTER_ACCESS_ENDED = [
    value for value in AfterAccessEnded.values if value != AfterAccessEnded.INHERIT
]


def _default_errors(defaults: dict[str, object]) -> list[str]:
    problems: list[str] = []
    if set(defaults) != set(CONFIG_FIELDS):
        problems.append(
            f"keys {sorted(defaults)} must be exactly {sorted(CONFIG_FIELDS)}"
        )
    for field in SWITCH_FIELDS:
        if field in defaults and not isinstance(defaults[field], bool):
            problems.append(f"{field} must be True or False, not {defaults[field]!r}")
    grace_window = defaults.get("grace_window")
    if "grace_window" in defaults and (
        not isinstance(grace_window, timedelta) or grace_window < timedelta(0)
    ):
        problems.append(
            f"grace_window must be a non-negative timedelta, not {grace_window!r}"
        )
    after_access_ended = defaults.get("after_access_ended")
    if (
        "after_access_ended" in defaults
        and after_access_ended not in _RESOLVED_AFTER_ACCESS_ENDED
    ):
        problems.append(
            f"after_access_ended must be one of {_RESOLVED_AFTER_ACCESS_ENDED}, "
            f"not {after_access_ended!r}"
        )
    return problems


@register()
def check_policy_defaults(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    return [
        Error(
            f"DEADLINE_POLICY_DEFAULTS: {problem}.",
            hint="Name every setting once, with a value the settings layer can decide with.",
            id="freedom_ls_deadlines.E001",
        )
        for problem in _default_errors(config.DEADLINE_POLICY_DEFAULTS)
    ]


def _names_an_uninstalled_fls_app(dotted: str) -> bool:
    """Whether `dotted` points into a freedom_ls app that isn't installed.

    Importing such a module would load its models, which raises RuntimeError rather
    than ImportError.
    """
    if not dotted.startswith("freedom_ls."):
        return False
    return apps.get_containing_app_config(dotted.rsplit(".", 1)[0]) is None


@register()
def check_policy_imports(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    dotted = config.DEADLINE_POLICY
    if _names_an_uninstalled_fls_app(dotted):
        return [
            Error(
                f"DEADLINE_POLICY {dotted!r} is not provided by any installed app.",
                hint="Add the app to INSTALLED_APPS, or point DEADLINE_POLICY at a policy you have installed.",
                id="freedom_ls_deadlines.E002",
            )
        ]
    try:
        policy_class = import_string(dotted)
    except ImportError:
        policy_class = None
    if isinstance(policy_class, type) and issubclass(policy_class, DeadlinePolicy):
        return []
    return [
        Error(
            f"DEADLINE_POLICY {dotted!r} is not an importable DeadlinePolicy subclass.",
            hint="Check the dotted path names a subclass of "
            "freedom_ls.deadlines.policy.DeadlinePolicy.",
            id="freedom_ls_deadlines.E002",
        )
    ]
