"""Tests for the panel_framework system checks."""

from __future__ import annotations

import gc
from pathlib import Path
from typing import cast

import pytest
from pytest_django.fixtures import SettingsWrapper

from django import forms
from django.contrib.sites.models import Site
from django.core.checks import CheckMessage, run_checks
from django.core.management import call_command
from django.tasks.backends.immediate import ImmediateBackend
from django.test import override_settings

from freedom_ls.panel_framework.checks import (
    REQUIRED_ICON_NAMES,
    check_icon_names,
    check_site_resolver,
    check_task_backend,
    default_sort_errors,
    editable_list_panel_errors,
    filter_key_errors,
    panel_errors,
    table_key_errors,
)
from freedom_ls.panel_framework.filters import BooleanFilter, TableFilter
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    EditableListPanel,
    Panel,
    PanelStack,
)
from freedom_ls.panel_framework.views import ListViewConfig

from .helpers import make_site
from .stub_models import StubChild, StubEntry, StubModel
from .stub_panels import StubDataTable


def test_unknown_field_name_raises_e001() -> None:
    # Arrange
    class BadFieldsPanel(Panel):
        model = StubModel
        fields = ["no_such_field"]

    # Act
    errors = panel_errors(BadFieldsPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E001"
    assert errors[0].obj is BadFieldsPanel


def test_fields_without_a_model_raises_e002() -> None:
    # Arrange
    class NoModelPanel(Panel):
        fields = ["name"]

    # Act
    errors = panel_errors(NoModelPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E002"
    assert errors[0].obj is NoModelPanel


def test_non_panel_child_raises_e003() -> None:
    # Arrange
    class NotAPanel:
        pass

    class BadChildPanel(Panel):
        children = {"bad": cast(type[Panel], NotAPanel)}

    # Act
    errors = panel_errors(BadChildPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E003"
    assert errors[0].obj is BadChildPanel


def test_a_property_field_raises_no_error() -> None:
    # Arrange
    class PropertyFieldPanel(Panel):
        model = StubModel
        fields = ["display_name"]

    # Act
    errors = panel_errors(PropertyFieldPanel)

    # Assert
    assert errors == []


def test_a_method_field_raises_no_error() -> None:
    # Arrange
    class MethodFieldPanel(Panel):
        model = StubModel
        fields = ["describe"]

    # Act
    errors = panel_errors(MethodFieldPanel)

    # Assert
    assert errors == []


def test_a_dunder_path_field_raises_no_error() -> None:
    # Arrange
    class DunderPathPanel(Panel):
        model = StubChild
        fields = ["parent__name"]

    # Act
    errors = panel_errors(DunderPathPanel)

    # Assert
    assert errors == []


def test_missing_table_key_raises_e004() -> None:
    # Arrange
    class NoKeyTablePanel(DataTablePanel):
        data_table = StubDataTable

    # Act
    errors = table_key_errors(NoKeyTablePanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E004"
    assert errors[0].obj is NoKeyTablePanel


def test_list_view_config_without_table_key_raises_e004() -> None:
    # Arrange
    class NoKeyListConfig(ListViewConfig):
        url_name = "no-key"
        menu_label = "No key"
        list_view = StubDataTable

    # Act
    errors = table_key_errors(NoKeyListConfig)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E004"
    assert errors[0].obj is NoKeyListConfig


def test_list_view_config_without_list_view_raises_no_error() -> None:
    # Arrange
    class NoListViewConfig(ListViewConfig):
        url_name = "no-list-view"
        menu_label = "No list view"

    # Act
    errors = table_key_errors(NoListViewConfig)

    # Assert
    assert errors == []


def test_a_section_outside_the_menu_with_no_list_raises_no_error() -> None:
    # Arrange
    class OutsideMenuConfig(ListViewConfig):
        url_name = "outside-menu"
        menu_label = "Outside menu"
        in_menu = False

    # Act
    errors = table_key_errors(OutsideMenuConfig)

    # Assert
    assert errors == []


def test_bad_table_key_format_raises_e005() -> None:
    # Arrange
    class BadKeyTablePanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "Bad Key!"

    # Act
    errors = table_key_errors(BadKeyTablePanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E005"
    assert errors[0].obj is BadKeyTablePanel


def test_valid_table_key_raises_no_error() -> None:
    # Arrange
    class GoodKeyTablePanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "good_key_1"

    # Act
    errors = table_key_errors(GoodKeyTablePanel)

    # Assert
    assert errors == []


def test_duplicate_table_keys_in_one_tree_raise_e006() -> None:
    # Arrange
    class FirstPanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "dupe"

    class SecondPanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "dupe"

    class Container(PanelStack):
        children = {"first": FirstPanel, "second": SecondPanel}

    # Act
    errors = table_key_errors(Container)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E006"
    assert errors[0].obj is Container


def test_same_key_in_separate_trees_is_allowed() -> None:
    # Arrange
    class OnePanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "shared"

    class OtherPanel(DataTablePanel):
        data_table = StubDataTable
        table_key = "shared"

    class FirstContainer(PanelStack):
        children = {"one": OnePanel}

    class SecondContainer(PanelStack):
        children = {"other": OtherPanel}

    # Act
    errors = table_key_errors(FirstContainer) + table_key_errors(SecondContainer)

    # Assert
    assert errors == []


def test_reserved_filter_key_raises_e007() -> None:
    # Arrange
    class ReservedFilterDataTable(StubDataTable):
        @staticmethod
        def get_filters() -> list[TableFilter]:
            return [BooleanFilter("page", "Page", lookup="is_active")]

    class ReservedFilterTablePanel(DataTablePanel):
        data_table = ReservedFilterDataTable
        table_key = "reserved_filter"

    # Act
    errors = filter_key_errors(ReservedFilterTablePanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E007"
    assert errors[0].obj is ReservedFilterTablePanel


def test_a_default_sort_on_a_field_no_column_sorts_by_raises_e008() -> None:
    # Arrange
    class BadDefaultSortDataTable(StubDataTable):
        default_sort = "kind"

    class BadDefaultSortTablePanel(DataTablePanel):
        data_table = BadDefaultSortDataTable
        table_key = "bad_default_sort"

    # Act
    errors = default_sort_errors(BadDefaultSortTablePanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E008"
    assert errors[0].obj is BadDefaultSortTablePanel


def test_a_descending_default_sort_on_a_sortable_column_raises_no_error() -> None:
    # Arrange
    class DescendingDefaultSortDataTable(StubDataTable):
        default_sort = "-name"

    class DescendingDefaultSortTablePanel(DataTablePanel):
        data_table = DescendingDefaultSortDataTable
        table_key = "descending_default_sort"

    # Act
    errors = default_sort_errors(DescendingDefaultSortTablePanel)

    # Assert
    assert errors == []


class _EntryForm(forms.ModelForm):
    class Meta:
        model = StubEntry
        fields = ["title", "detail"]


# The event every list below sends, so each test fails on one condition only.
_REFRESH_EVENTS = ("entryChanged",)


def test_editable_list_panel_itself_raises_no_error() -> None:
    # Act
    errors = editable_list_panel_errors(EditableListPanel)

    # Assert
    assert errors == []


def test_a_well_formed_editable_list_panel_raises_no_error() -> None:
    # Arrange
    class WellFormedListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS
        form_class = _EntryForm
        parent_field = "parent"
        max_entries = 3
        layout = "table"

    # Act
    errors = editable_list_panel_errors(WellFormedListPanel)

    # Assert
    assert errors == []


def test_an_editable_list_panel_without_form_class_raises_e009() -> None:
    # Arrange
    class NoFormListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS
        parent_field = "parent"

    # Act
    errors = editable_list_panel_errors(NoFormListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is NoFormListPanel


def test_an_editable_list_panel_with_a_plain_form_raises_e009() -> None:
    # Arrange
    PlainFormListPanel = type(
        "PlainFormListPanel",
        (EditableListPanel,),
        {
            "refresh_events": _REFRESH_EVENTS,
            "form_class": forms.Form,
            "parent_field": "parent",
        },
    )

    # Act
    errors = editable_list_panel_errors(PlainFormListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is PlainFormListPanel


def test_a_parent_field_missing_from_the_model_raises_e009() -> None:
    # Arrange
    class MissingParentListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS
        form_class = _EntryForm
        parent_field = "no_such_field"

    # Act
    errors = editable_list_panel_errors(MissingParentListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is MissingParentListPanel


def test_a_parent_field_that_is_not_a_foreign_key_raises_e009() -> None:
    # Arrange
    class NotForeignKeyListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS
        form_class = _EntryForm
        parent_field = "title"

    # Act
    errors = editable_list_panel_errors(NotForeignKeyListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is NotForeignKeyListPanel


def test_a_form_that_lists_the_parent_field_raises_e009() -> None:
    # Arrange
    class ParentInFormListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS

        class form_class(forms.ModelForm):  # noqa: N801
            class Meta:
                model = StubEntry
                fields = ["parent", "title"]

        parent_field = "parent"

    # Act
    errors = editable_list_panel_errors(ParentInFormListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is ParentInFormListPanel


@pytest.mark.parametrize("max_entries", [0, -1, "3", True])
def test_a_bad_max_entries_raises_e009(max_entries: object) -> None:
    # Arrange
    BadCapListPanel = type(
        "BadCapListPanel",
        (EditableListPanel,),
        {
            "refresh_events": _REFRESH_EVENTS,
            "form_class": _EntryForm,
            "parent_field": "parent",
            "max_entries": max_entries,
        },
    )

    # Act
    errors = editable_list_panel_errors(BadCapListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is BadCapListPanel


@pytest.mark.parametrize("layout", ["grid", "", None])
def test_a_bad_layout_raises_e009(layout: object) -> None:
    # Arrange
    BadLayoutListPanel = type(
        "BadLayoutListPanel",
        (EditableListPanel,),
        {
            "refresh_events": _REFRESH_EVENTS,
            "form_class": _EntryForm,
            "parent_field": "parent",
            "layout": layout,
        },
    )

    # Act
    errors = editable_list_panel_errors(BadLayoutListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is BadLayoutListPanel


def test_an_editable_list_panel_without_refresh_events_raises_e009() -> None:
    # Arrange
    class NoRefreshListPanel(EditableListPanel):
        form_class = _EntryForm
        parent_field = "parent"

    # Act
    errors = editable_list_panel_errors(NoRefreshListPanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E009"
    assert errors[0].obj is NoRefreshListPanel
    assert "refresh_events" in errors[0].msg


def test_a_panel_that_overrides_get_form_class_raises_no_form_error() -> None:
    # Arrange
    class PerRequestFormListPanel(EditableListPanel):
        refresh_events = _REFRESH_EVENTS
        parent_field = "parent"

        def get_form_class(self) -> type[forms.ModelForm]:
            return _EntryForm

    # Act
    errors = editable_list_panel_errors(PerRequestFormListPanel)

    # Assert
    assert errors == []


def test_bad_filter_key_format_raises_e007() -> None:
    # Arrange
    class BadFilterDataTable(StubDataTable):
        @staticmethod
        def get_filters() -> list[TableFilter]:
            return [BooleanFilter("Bad Key!", "Bad", lookup="is_active")]

    class BadFilterTablePanel(DataTablePanel):
        data_table = BadFilterDataTable
        table_key = "bad_filter"

    # Act
    errors = filter_key_errors(BadFilterTablePanel)

    # Assert
    assert len(errors) == 1
    assert errors[0].id == "freedom_ls_panel_framework.E007"
    assert errors[0].obj is BadFilterTablePanel


def test_valid_filter_key_raises_no_error() -> None:
    # Arrange
    class GoodFilterDataTable(StubDataTable):
        @staticmethod
        def get_filters() -> list[TableFilter]:
            return [BooleanFilter("good_key_1", "Good", lookup="is_active")]

    class GoodFilterTablePanel(DataTablePanel):
        data_table = GoodFilterDataTable
        table_key = "good_filter"

    # Act
    errors = filter_key_errors(GoodFilterTablePanel)

    # Assert
    assert errors == []


@pytest.mark.django_db
def test_call_command_check_passes_on_the_real_config() -> None:
    # The fixture panels above are defined inside test functions so they are
    # never module-level Panel subclasses, but a class lingers in
    # Panel.__subclasses__() until the garbage collector frees it.
    gc.collect()

    call_command("check")


class LocalImmediateBackend(ImmediateBackend):
    """A host's own subclass of a backend that runs tasks inline."""


@pytest.mark.parametrize(
    "backend",
    [
        "django.tasks.backends.immediate.ImmediateBackend",
        "django.tasks.backends.dummy.DummyBackend",
        "django_tasks.backends.immediate.ImmediateBackend",
        "django_tasks.backends.dummy.DummyBackend",
        f"{__name__}.LocalImmediateBackend",
    ],
)
def test_non_durable_task_backend_warns_w001(backend: str) -> None:
    # Arrange
    tasks = {"default": {"BACKEND": backend}}

    # Act
    with override_settings(DEBUG=False, TASKS=tasks):
        messages = check_task_backend(app_configs=None)

    # Assert
    assert len(messages) == 1
    assert messages[0].id == "freedom_ls_panel_framework.W001"
    assert backend in messages[0].msg


@pytest.mark.parametrize(
    ("debug", "tasks"),
    [
        (
            True,
            {
                "default": {
                    "BACKEND": "django.tasks.backends.immediate.ImmediateBackend"
                }
            },
        ),
        (False, {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}),
        (False, {}),
        (False, {"default": {}}),
    ],
    ids=["debug_on", "durable_backend", "no_tasks", "no_backend_key"],
)
def test_task_backend_check_is_silent_when_nothing_is_wrong(
    debug: bool, tasks: dict[str, dict[str, str]]
) -> None:
    # Arrange / Act
    with override_settings(DEBUG=debug, TASKS=tasks):
        messages = check_task_backend(app_configs=None)

    # Assert
    assert messages == []


@pytest.mark.django_db
def test_non_durable_task_backend_warning_is_registered_with_run_checks() -> None:
    # Arrange
    tasks = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}

    # Act
    with override_settings(DEBUG=False, TASKS=tasks):
        message_ids = [message.id for message in run_checks()]

    # Assert
    assert "freedom_ls_panel_framework.W001" in message_ids


@pytest.fixture
def default_resolver(settings: SettingsWrapper) -> None:
    """Drop the project's resolver so the framework's declared default applies."""
    if hasattr(settings, "PANEL_FRAMEWORK_SITE_RESOLVER"):
        del settings.PANEL_FRAMEWORK_SITE_RESOLVER


@pytest.fixture
def two_sites() -> None:
    make_site("North", "north.test")
    make_site("South", "south.test")


@pytest.mark.django_db
@pytest.mark.usefixtures("default_resolver", "two_sites")
def test_site_id_with_the_default_resolver_on_several_sites_warns_w002(
    settings: SettingsWrapper,
) -> None:
    settings.SITE_ID = 1

    messages = check_site_resolver(app_configs=None, databases=["default"])

    assert [message.id for message in messages] == ["freedom_ls_panel_framework.W002"]


@pytest.mark.django_db
@pytest.mark.usefixtures("default_resolver", "two_sites")
def test_the_site_resolver_check_reads_no_database_unless_asked(
    settings: SettingsWrapper,
) -> None:
    settings.SITE_ID = 1

    assert check_site_resolver(app_configs=None, databases=None) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("default_resolver")
def test_the_site_resolver_check_is_silent_with_one_site(
    settings: SettingsWrapper,
) -> None:
    site = Site.objects.first() or make_site("Only", "only.test")
    assert Site.objects.count() == 1
    settings.SITE_ID = site.pk

    assert check_site_resolver(app_configs=None, databases=["default"]) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("default_resolver", "two_sites")
def test_the_site_resolver_check_is_silent_without_site_id(
    settings: SettingsWrapper,
) -> None:
    settings.SITE_ID = None

    assert check_site_resolver(app_configs=None, databases=["default"]) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("two_sites")
def test_the_site_resolver_check_is_silent_with_a_resolver_of_the_hosts_own(
    settings: SettingsWrapper,
) -> None:
    settings.SITE_ID = 1
    settings.PANEL_FRAMEWORK_SITE_RESOLVER = "some.host.resolver"

    assert check_site_resolver(app_configs=None, databases=["default"]) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("default_resolver", "two_sites")
def test_the_site_resolver_warning_is_registered_for_database_checks(
    settings: SettingsWrapper,
) -> None:
    settings.SITE_ID = 1

    message_ids = [message.id for message in run_checks(databases=["default"])]

    assert "freedom_ls_panel_framework.W002" in message_ids


FAILING_NAMES = ("close", "next")


def _put_icon_component_first(
    tmp_path: Path, settings: SettingsWrapper, source: str
) -> None:
    (tmp_path / "cotton").mkdir()
    (tmp_path / "cotton" / "panel-icon.html").write_text(source)
    settings.TEMPLATES[0]["DIRS"] = [str(tmp_path), *settings.TEMPLATES[0]["DIRS"]]


def _run_icon_check() -> list[CheckMessage]:
    return check_icon_names(app_configs=None)


def test_an_icon_component_that_includes_a_missing_template_raises_e010(
    tmp_path: Path, settings: SettingsWrapper
) -> None:
    _put_icon_component_first(tmp_path, settings, '{% include "no_such_icon.html" %}')

    messages = _run_icon_check()

    assert {message.id for message in messages} == {"freedom_ls_panel_framework.E010"}
    assert len(messages) == len(REQUIRED_ICON_NAMES)


def test_an_icon_component_that_renders_nothing_raises_w003(
    tmp_path: Path, settings: SettingsWrapper
) -> None:
    _put_icon_component_first(tmp_path, settings, "")

    messages = _run_icon_check()

    assert {message.id for message in messages} == {"freedom_ls_panel_framework.W003"}
    assert len(messages) == len(REQUIRED_ICON_NAMES)


def test_the_shipped_icon_primitive_raises_no_icon_message() -> None:
    assert _run_icon_check() == []


def test_each_failing_icon_name_gets_one_error_naming_it(
    tmp_path: Path, settings: SettingsWrapper
) -> None:
    _put_icon_component_first(
        tmp_path,
        settings,
        '<c-vars name="" />{% if name == "close" or name == "next" %}'
        '{% include "no_such_icon.html" %}{% else %}<svg></svg>{% endif %}',
    )

    messages = _run_icon_check()

    assert [message.id for message in messages] == [
        "freedom_ls_panel_framework.E010"
    ] * len(FAILING_NAMES)
    assert [
        message.msg.count(f"'{name}'")
        for name, message in zip(FAILING_NAMES, messages, strict=True)
    ] == [1, 1]


def test_a_required_name_with_no_icon_body_raises_e010(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "freedom_ls.panel_framework.checks.REQUIRED_ICON_NAMES",
        REQUIRED_ICON_NAMES | {"no_such_semantic_icon"},
    )

    messages = _run_icon_check()

    assert [message.id for message in messages] == ["freedom_ls_panel_framework.E010"]
    assert "no_such_semantic_icon" in messages[0].msg


@pytest.mark.parametrize(
    "error",
    [ValueError("unknown icon set"), FileNotFoundError("no iconify JSON")],
    ids=["ValueError", "FileNotFoundError"],
)
def test_an_icon_component_that_raises_a_backend_error_raises_e010(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def _raise(name: str) -> str:
        raise error

    monkeypatch.setattr("freedom_ls.panel_framework.checks._render_icon", _raise)

    messages = _run_icon_check()

    assert {message.id for message in messages} == {"freedom_ls_panel_framework.E010"}
    assert len(messages) == len(REQUIRED_ICON_NAMES)
