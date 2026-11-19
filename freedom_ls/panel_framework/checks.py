"""System checks that validate every `Panel` subclass reachable from the project."""

from __future__ import annotations

import re
from collections.abc import Sequence
from importlib import import_module

from django_cotton.compiler_regex import CottonCompiler

from django.apps import AppConfig
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.checks import CheckMessage, Error, Warning
from django.template import Context, Template, TemplateDoesNotExist, TemplateSyntaxError
from django.template.loader import get_template
from django.utils.module_loading import import_string

from freedom_ls.panel_framework.config import PanelFrameworkConfig, config
from freedom_ls.panel_framework.field_display import label_for_field
from freedom_ls.panel_framework.panels import DataTablePanel, Panel
from freedom_ls.panel_framework.tables import DataTable

# Deferred: views.py imports panels.py and tables.py, not this module, so
# importing it here carries no cycle.
from freedom_ls.panel_framework.views import ListViewConfig, ListViewPanel

_TABLE_KEY_PATTERN = re.compile(r"^[a-z0-9_]+$")
_RESERVED_FILTER_KEYS = {"q", "sort", "page", "export"}

# Backends that run a task inline or never: Django's own and the django_tasks
# backport's. The backport is optional, so a path that does not import is
# skipped.
_NON_DURABLE_BACKEND_PATHS = (
    "django.tasks.backends.immediate.ImmediateBackend",
    "django.tasks.backends.dummy.DummyBackend",
    "django_tasks.backends.immediate.ImmediateBackend",
    "django_tasks.backends.dummy.DummyBackend",
)

# Every icon name the framework's templates and primitives draw, which the
# host's `c-icon` must be able to render. Names bound at runtime
# (`:name="item.icon"`) are the host's own and are not listed.
REQUIRED_ICON_NAMES: frozenset[str] = frozenset(
    {
        "add",
        "check",
        "close",
        "download",
        "dropdown",
        "error",
        "filter",
        "info",
        "loading",
        "menu",
        "more_options",
        "next",
        "open_page",
        "previous",
        "quick_view",
        "retry",
        "search",
        "settings",
        "sort_asc",
        "sort_desc",
        "sort_neutral",
        "success",
        "trend_down",
        "trend_up",
        "user",
        "warning",
    }
)


def _importable_classes(paths: Sequence[str]) -> tuple[type, ...]:
    classes: list[type] = []
    for path in paths:
        try:
            imported = import_string(path)
        except ImportError:
            continue
        if isinstance(imported, type):
            classes.append(imported)
    return tuple(classes)


def check_task_backend(
    *,
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Warn when background bulk actions would run inline or not at all."""
    backend = settings.TASKS.get("default", {}).get("BACKEND", "")
    if settings.DEBUG or not backend:
        return []
    try:
        backend_class = import_string(backend)
    except ImportError:
        # Django's own task setup reports a backend that does not import.
        return []
    non_durable = _importable_classes(_NON_DURABLE_BACKEND_PATHS)
    if not (isinstance(backend_class, type) and issubclass(backend_class, non_durable)):
        return []
    return [
        Warning(
            f"TASKS['default'] uses {backend}.",
            hint=(
                "Bulk actions over BULK_BACKGROUND_THRESHOLD rows run as background "
                "tasks and need a durable backend with a worker. Add "
                "freedom_ls_panel_framework.W001 to SILENCED_SYSTEM_CHECKS if "
                "this is intended."
            ),
            id="freedom_ls_panel_framework.W001",
        )
    ]


def _render_icon(name: str) -> str:
    """The host's c-icon for `name`, rendered. A string template is never
    compiled by cotton's loader, so the tag is compiled here."""
    source = CottonCompiler().process(f'<c-icon name="{name}" />')
    return Template(source).render(Context())


def check_icon_names(
    *,
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Report each icon name the framework draws that the host's c-icon cannot."""
    messages: list[CheckMessage] = []
    for name in sorted(REQUIRED_ICON_NAMES):
        hint = f"Make the host's c-icon draw '{name}'. See HOST_CONTRACT.md#icons."
        try:
            rendered = _render_icon(name)
        except (TemplateDoesNotExist, TemplateSyntaxError, LookupError) as error:
            messages.append(
                Error(
                    f"The host's c-icon cannot draw the icon '{name}': {error!r}.",
                    hint=hint,
                    id="freedom_ls_panel_framework.E010",
                )
            )
            continue
        if not rendered.strip():
            messages.append(
                Warning(
                    f"The host's c-icon draws nothing for the icon '{name}'.",
                    hint=hint,
                    id="freedom_ls_panel_framework.W003",
                )
            )
    return messages


def check_site_resolver(
    *,
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Warn when SITE_ID decides every request's site on a database that
    holds several sites.

    The default resolver follows django.contrib.sites, where SITE_ID wins
    over the request's host, so every site's bulk runs would be recorded
    under one. Counting sites needs the database, which Django offers a
    check only under `migrate` or `check --database`.
    """
    default = PanelFrameworkConfig.declared_settings[
        "PANEL_FRAMEWORK_SITE_RESOLVER"
    ].default
    resolver = config.PANEL_FRAMEWORK_SITE_RESOLVER
    site_id = getattr(settings, "SITE_ID", None)
    if databases is None or site_id is None or resolver != default:
        return []
    if not any(Site.objects.using(alias).count() > 1 for alias in databases):
        return []
    return [
        Warning(
            f"SITE_ID = {site_id!r} decides the site of every bulk-action "
            "run, but the database holds several sites.",
            hint=(
                "Set PANEL_FRAMEWORK_SITE_RESOLVER to a resolver that reads the "
                "request's host, or add freedom_ls_panel_framework.W002 to "
                "SILENCED_SYSTEM_CHECKS if every request really is one site."
            ),
            id="freedom_ls_panel_framework.W002",
        )
    ]


def check_reference_base_template(
    *,
    app_configs: Sequence[AppConfig] | None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Report a PANEL_REFERENCE_BASE_TEMPLATE that does not load."""
    name = config.PANEL_REFERENCE_BASE_TEMPLATE
    try:
        get_template(name)
    except TemplateDoesNotExist:
        return [
            Error(
                f"PANEL_REFERENCE_BASE_TEMPLATE = {name!r} does not exist.",
                hint=(
                    "Set PANEL_REFERENCE_BASE_TEMPLATE to a template that defines "
                    "the head_title and content blocks; see "
                    "HOST_CONTRACT.md#reference-page."
                ),
                id="freedom_ls_panel_framework.E009",
            )
        ]
    return []


def check_panels(
    *,
    app_configs: Sequence[AppConfig] | None,
    databases: Sequence[str] | None = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Validate every `Panel` and `ListViewConfig` subclass reachable from
    `settings.ROOT_URLCONF`.

    Importing the root URLconf first ensures every consumer's panel module has
    run and registered its subclasses, since the framework keeps no registry
    of its own.
    """
    import_module(settings.ROOT_URLCONF)
    errors: list[CheckMessage] = []
    for panel_class in _all_subclasses(Panel):
        errors.extend(panel_errors(panel_class))
        errors.extend(table_key_errors(panel_class))
        errors.extend(filter_key_errors(panel_class))
        errors.extend(default_sort_errors(panel_class))
    for config_class in _all_subclasses(ListViewConfig):
        errors.extend(table_key_errors(config_class))
        errors.extend(filter_key_errors(config_class))
        errors.extend(default_sort_errors(config_class))
    return errors


def _all_subclasses(base: type) -> list[type]:
    """Every subclass reachable from `base` itself, without duplicates."""
    seen: dict[type, None] = {}
    stack = list(base.__subclasses__())
    while stack:
        subclass = stack.pop()
        if subclass in seen:
            continue
        seen[subclass] = None
        stack.extend(subclass.__subclasses__())
    return list(seen)


def panel_errors(panel_class: type[Panel]) -> list[CheckMessage]:
    """Validate one Panel subclass's `fields`, `model` and `children` declarations."""
    errors: list[CheckMessage] = []
    # Only some panels (InstanceDetailsPanel and its kind) declare fields.
    fields: list[str] = getattr(panel_class, "fields", [])
    model = panel_class.model

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

    children: dict[str, object] = dict(panel_class.children)
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


def table_key_errors(cls: type) -> list[CheckMessage]:
    """Validate `table_key` on one `DataTablePanel` or `ListViewConfig`
    subclass, and — for a container — that its descendant `DataTablePanel`s
    don't share one with each other.

    Called once per class `check_panels` finds, so a `DataTablePanel` and a
    `ListViewConfig` are each checked on their own terms: a `DataTablePanel`
    always needs one (`ListViewPanel` is the sole exemption, since its key
    comes from the `ListViewConfig` it binds to at request time), while a
    `ListViewConfig` needs one only when it declares `list_view`.
    """
    errors: list[CheckMessage] = []
    if issubclass(cls, ListViewConfig) and cls.list_view is not None:
        errors.extend(_check_table_key_format(cls, getattr(cls, "table_key", None)))
    if issubclass(cls, Panel):
        if issubclass(cls, DataTablePanel) and cls not in (
            DataTablePanel,
            ListViewPanel,
        ):
            errors.extend(_check_table_key_format(cls, getattr(cls, "table_key", None)))
        if cls.children:
            errors.extend(_check_no_duplicate_table_keys(cls))
    return errors


def _check_table_key_format(cls: type, table_key: str | None) -> list[CheckMessage]:
    if not table_key:
        return [
            Error(
                f"{cls.__name__} has no table_key.",
                hint="Set a table_key of lowercase letters, digits and underscores.",
                id="freedom_ls_panel_framework.E004",
                obj=cls,
            )
        ]
    if not _TABLE_KEY_PATTERN.fullmatch(table_key):
        return [
            Error(
                f"{cls.__name__}.table_key '{table_key}' must match "
                f"'{_TABLE_KEY_PATTERN.pattern}'.",
                hint="Use only lowercase letters, digits and underscores.",
                id="freedom_ls_panel_framework.E005",
                obj=cls,
            )
        ]
    return []


def _descendant_table_keys(panel_class: type[Panel]) -> list[str]:
    """Every table_key of a DataTablePanel reachable from `panel_class`'s
    `children`, walked recursively, in the order encountered."""
    keys: list[str] = []
    children: dict[str, object] = dict(panel_class.children)
    for child_class in children.values():
        if not (isinstance(child_class, type) and issubclass(child_class, Panel)):
            continue  # Not a Panel subclass at all: already reported as E003.
        if issubclass(child_class, DataTablePanel):
            table_key = getattr(child_class, "table_key", None)
            if table_key:
                keys.append(table_key)
        if child_class.children:
            keys.extend(_descendant_table_keys(child_class))
    return keys


def _check_no_duplicate_table_keys(panel_class: type[Panel]) -> list[CheckMessage]:
    keys = _descendant_table_keys(panel_class)
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if not duplicates:
        return []
    return [
        Error(
            f"{panel_class.__name__}'s descendant tables share the key(s) "
            f"{', '.join(duplicates)}.",
            hint="Give each DataTablePanel a unique table_key within one container.",
            id="freedom_ls_panel_framework.E006",
            obj=panel_class,
        )
    ]


def _reachable_data_table(cls: type) -> type[DataTable] | None:
    """The `DataTable` `cls` binds, if any: a `ListViewConfig`'s `list_view`
    or a `DataTablePanel`'s `data_table`. `None` for every other class, and
    for the two `DataTablePanel`s that bind theirs at request time rather
    than declaring one."""
    if issubclass(cls, ListViewConfig) and cls.list_view is not None:
        return cls.list_view
    if (
        issubclass(cls, Panel)
        and issubclass(cls, DataTablePanel)
        and cls not in (DataTablePanel, ListViewPanel)
    ):
        return getattr(cls, "data_table", None)
    return None


def filter_key_errors(cls: type) -> list[CheckMessage]:
    """Validate every filter key a `DataTable` reachable from `cls` declares.

    Called on the same classes `table_key_errors` is, so a `DataTablePanel`
    and a `ListViewConfig` sharing one `DataTable` each report the same
    error, the way `panel_errors` repeats a fields error for two panels
    sharing a model.
    """
    data_table = _reachable_data_table(cls)
    if data_table is None:
        return []
    errors: list[CheckMessage] = []
    for table_filter in data_table.get_filters():
        if (
            _TABLE_KEY_PATTERN.fullmatch(table_filter.key)
            and table_filter.key not in _RESERVED_FILTER_KEYS
        ):
            continue
        errors.append(
            Error(
                f"{cls.__name__}'s {data_table.__name__} declares a filter "
                f"key '{table_filter.key}', which must match "
                f"'{_TABLE_KEY_PATTERN.pattern}' and must not be one of "
                f"{', '.join(sorted(_RESERVED_FILTER_KEYS))}.",
                hint="Use a filter key of lowercase letters, digits and "
                "underscores, other than q, sort, page or export.",
                id="freedom_ls_panel_framework.E007",
                obj=cls,
            )
        )
    return errors


def default_sort_errors(cls: type) -> list[CheckMessage]:
    """Validate the `default_sort` of the `DataTable` reachable from `cls`:
    it must name a field one of the table's sortable columns sorts by, or a
    header would never read as sorted and the first click would repeat the
    order on screen."""
    data_table = _reachable_data_table(cls)
    if data_table is None or not data_table.default_sort:
        return []
    sort_field = data_table.default_sort.removeprefix("-")
    sortable_fields = {
        column.sort_field for column in data_table.get_columns() if column.sortable
    }
    if sort_field in sortable_fields:
        return []
    return [
        Error(
            f"{cls.__name__}'s {data_table.__name__} declares default_sort "
            f"'{data_table.default_sort}', but no sortable column sorts by "
            f"'{sort_field}'.",
            hint="Use the sort_field of a sortable column, with a leading '-' "
            "for descending.",
            id="freedom_ls_panel_framework.E008",
            obj=cls,
        )
    ]
