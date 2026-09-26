"""Tests for PanelContext."""

from __future__ import annotations

import dataclasses

import pytest

from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext


def test_panel_context_field_assignment_raises_frozen_instance_error() -> None:
    # Arrange
    request = RequestFactory().get("/cohorts/1")
    ctx = PanelContext(request=request, instance=None, base_url="cohorts/1", name="")

    # Act / Assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ctx, "name", "changed")  # noqa: B010


def test_replace_builds_a_distinct_context_for_a_child() -> None:
    # Arrange
    request = RequestFactory().get("/cohorts/1")
    parent = PanelContext(request=request, instance=None, base_url="cohorts/1", name="")

    # Act
    child = dataclasses.replace(
        parent, base_url="cohorts/1/__panels/details", name="details"
    )

    # Assert
    assert child.name == "details"
    assert parent.name == ""
