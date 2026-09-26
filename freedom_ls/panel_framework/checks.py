"""System checks that validate every `Panel` subclass reachable from the project."""

from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module

from django.apps import AppConfig
from django.conf import settings
from django.core.checks import CheckMessage, Error

from freedom_ls.panel_framework.field_display import label_for_field
from freedom_ls.panel_framework.panels import Panel


def check_panels(
    *,
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Validate every `Panel` subclass reachable from `settings.ROOT_URLCONF`.

    Importing the root URLconf first ensures every consumer's panel module has
    run and registered its `Panel` subclasses, since the framework keeps no
    registry of its own.
    """
    import_module(settings.ROOT_URLCONF)
    errors: list[CheckMessage] = []
    for panel_class in _all_panel_classes():
        errors.extend(panel_errors(panel_class))
    return errors


def _all_panel_classes() -> list[type[Panel]]:
    """Every Panel subclass reachable from Panel itself, without duplicates."""
    seen: dict[type[Panel], None] = {}
    stack = list(Panel.__subclasses__())
    while stack:
        panel_class = stack.pop()
        if panel_class in seen:
            continue
        seen[panel_class] = None
        stack.extend(panel_class.__subclasses__())
    return list(seen)


def panel_errors(panel_class: type[Panel]) -> list[CheckMessage]:
    """Validate one Panel subclass's `fields`, `model` and `children` declarations."""
    errors: list[CheckMessage] = []
    fields: list[str] = getattr(panel_class, "fields", [])
    model = getattr(panel_class, "model", None)

    if fields and model is None:
        errors.append(
            Error(
                f"{panel_class.__name__} declares fields but no model.",
                hint=f"Set {panel_class.__name__}.model.",
                id="freedom_ls_panel_framework.E002",
                obj=panel_class,
            )
        )
    elif model is not None:
        for i, name in enumerate(fields):
            try:
                label_for_field(name, model)
            except AttributeError:
                errors.append(
                    Error(
                        f"{panel_class.__name__}.fields[{i}] refers to '{name}', "
                        f"which is not a field, property or method on "
                        f"'{model._meta.label}'.",
                        hint="Use a field name or a '__' path through relations.",
                        id="freedom_ls_panel_framework.E001",
                        obj=panel_class,
                    )
                )

    children: dict[str, object] = getattr(panel_class, "children", {})
    for key, value in children.items():
        if not (isinstance(value, type) and issubclass(value, Panel)):
            errors.append(
                Error(
                    f"{panel_class.__name__}.children['{key}'] is not a Panel subclass.",
                    id="freedom_ls_panel_framework.E003",
                    obj=panel_class,
                )
            )

    return errors
