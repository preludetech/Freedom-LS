"""Tests for the panel_framework system checks."""

from __future__ import annotations

import gc
from typing import cast

import pytest

from django.core.management import call_command

from freedom_ls.panel_framework.checks import (
    filter_key_errors,
    panel_errors,
    table_key_errors,
)
from freedom_ls.panel_framework.filters import BooleanFilter, TableFilter
from freedom_ls.panel_framework.panels import DataTablePanel, Panel, PanelStack
from freedom_ls.panel_framework.views import ListViewConfig

from .conftest import StubChild, StubModel
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
