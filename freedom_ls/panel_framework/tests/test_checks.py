"""Tests for the panel_framework system checks."""

from __future__ import annotations

from freedom_ls.panel_framework.checks import panel_errors
from freedom_ls.panel_framework.panels import Panel

from .conftest import StubChild, StubModel


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
        children = {"bad": NotAPanel}

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
