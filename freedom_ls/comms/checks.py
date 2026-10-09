"""Django system checks for the comms app.

E001 — Two registered notification categories share a key.
E002 — A NOTIFICATION_DELIVERY_BACKENDS path that doesn't import.
E003 — MESSAGING_POLICY doesn't import, or isn't a MessagingPolicy subclass.
       A path into an FLS app that isn't installed is left to E004.
E004 — MESSAGING_POLICY names an FLS app that isn't installed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from django.apps import AppConfig, apps
from django.core.checks import CheckMessage, Error, register
from django.utils.module_loading import import_string

from freedom_ls.comms.config import config
from freedom_ls.comms.messaging_policy import MessagingPolicy


@register()
def check_notification_category_keys_are_unique(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    keys = [category.key for category in config.NOTIFICATION_CATEGORIES]
    counts = Counter(keys)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if not duplicates:
        return []

    return [
        Error(
            f"NOTIFICATION_CATEGORIES has duplicate keys: {duplicates}.",
            hint="Each notification category's key must be unique.",
            id="freedom_ls_comms.E001",
        )
    ]


@register()
def check_notification_delivery_backends_import(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    errors: list[CheckMessage] = []
    for backend_path in config.NOTIFICATION_DELIVERY_BACKENDS:
        try:
            import_string(backend_path)
        except ImportError:
            errors.append(
                Error(
                    f"NOTIFICATION_DELIVERY_BACKENDS path {backend_path!r} could not be imported.",
                    hint="Check the dotted path names an importable class.",
                    id="freedom_ls_comms.E002",
                )
            )
    return errors


def _comms_not_being_checked(app_configs: Sequence[AppConfig] | None) -> bool:
    return app_configs is not None and not any(
        c.label == "freedom_ls_comms" for c in app_configs
    )


def _names_an_uninstalled_fls_app(dotted: str) -> bool:
    """Whether `dotted` points into a freedom_ls app that isn't installed.

    A downstream's own policy lives outside any FLS app; whether it loads is
    E003's question.
    """
    if not dotted.startswith("freedom_ls."):
        return False
    return apps.get_containing_app_config(dotted.rsplit(".", 1)[0]) is None


@register()
def check_messaging_policy_imports(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E003: error when MESSAGING_POLICY isn't an importable MessagingPolicy subclass."""
    if _comms_not_being_checked(app_configs):
        return []
    dotted = config.MESSAGING_POLICY
    if _names_an_uninstalled_fls_app(dotted):
        # E004 reports this. Importing the module would also load its models,
        # which raises RuntimeError rather than ImportError when the app is
        # not installed.
        return []
    try:
        policy_class = import_string(dotted)
    except ImportError:
        policy_class = None
    if isinstance(policy_class, type) and issubclass(policy_class, MessagingPolicy):
        return []
    return [
        Error(
            f"MESSAGING_POLICY {dotted!r} is not an importable MessagingPolicy subclass.",
            hint="Check the dotted path names a subclass of "
            "freedom_ls.comms.messaging_policy.MessagingPolicy.",
            id="freedom_ls_comms.E003",
        )
    ]


@register()
def check_messaging_policy_app_installed(
    app_configs: Sequence[AppConfig] | None, **kwargs: object
) -> list[CheckMessage]:
    """E004: error when MESSAGING_POLICY names an FLS app that isn't installed."""
    if _comms_not_being_checked(app_configs):
        return []
    dotted = config.MESSAGING_POLICY
    if not _names_an_uninstalled_fls_app(dotted):
        return []
    return [
        Error(
            f"MESSAGING_POLICY {dotted!r} is not provided by any installed app.",
            hint="Add freedom_ls.messaging_policy to INSTALLED_APPS, or point MESSAGING_POLICY at a policy you have installed.",
            id="freedom_ls_comms.E004",
        )
    ]
