"""Tests for PanelContext."""

from __future__ import annotations

import dataclasses

import pytest

from django.contrib.sites.models import Site
from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.views import SectionConfigBase


def test_panel_context_field_assignment_raises_frozen_instance_error() -> None:
    # Arrange
    request = RequestFactory().get("/cohorts/1")
    ctx = PanelContext(
        request=request,
        instance=None,
        base_url="cohorts/1",
        name="",
        config=SectionConfigBase,
    )

    # Act / Assert
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(ctx, "name", "changed")  # noqa: B010


def test_replace_builds_a_distinct_context_for_a_child() -> None:
    # Arrange
    request = RequestFactory().get("/cohorts/1")
    parent = PanelContext(
        request=request,
        instance=None,
        base_url="cohorts/1",
        name="",
        config=SectionConfigBase,
    )

    # Act
    child = dataclasses.replace(
        parent, base_url="cohorts/1/__panels/details", name="details"
    )

    # Assert
    assert child.name == "details"
    assert parent.name == ""


def test_scope_object_prefers_the_instance_over_the_scope() -> None:
    request = RequestFactory().get("/cohorts/1")
    instance = Site(name="Instance")
    ctx = PanelContext(
        request=request,
        instance=instance,
        base_url="cohorts/1",
        name="",
        config=SectionConfigBase,
        scope=Site(name="Scope"),
    )

    assert ctx.scope_object() is instance


def test_scope_object_falls_back_to_scope_with_no_instance() -> None:
    request = RequestFactory().get("/cohorts")
    scope = Site(name="Scope")
    ctx = PanelContext(
        request=request,
        instance=None,
        base_url="cohorts",
        name="",
        config=SectionConfigBase,
        scope=scope,
    )

    assert ctx.scope_object() is scope


def _context() -> PanelContext:
    return PanelContext(
        request=RequestFactory().get("/cohorts/1"),
        instance=None,
        base_url="cohorts/1",
        name="",
        config=SectionConfigBase,
    )


def test_once_loads_a_value_the_first_time_and_returns_it_after() -> None:
    ctx = _context()
    loads: list[str] = []

    def load() -> str:
        loads.append("loaded")
        return "row"

    values = [ctx.once("row", load), ctx.once("row", load)]

    assert values == ["row", "row"]
    assert loads == ["loaded"]


def test_once_keeps_a_none_it_loaded() -> None:
    ctx = _context()
    loads: list[str] = []

    def load() -> None:
        loads.append("loaded")

    ctx.once("absent", load)
    ctx.once("absent", load)

    assert loads == ["loaded"]


def test_once_keeps_each_key_apart() -> None:
    ctx = _context()

    assert (ctx.once("a", lambda: 1), ctx.once("b", lambda: 2)) == (1, 2)


def test_a_replaced_context_reads_what_the_original_loaded() -> None:
    ctx = _context()
    ctx.once("row", lambda: "first")

    replaced = dataclasses.replace(ctx, reason="Merged")

    assert replaced.once("row", lambda: "second") == "first"


def test_a_load_that_raises_is_tried_again() -> None:
    ctx = _context()

    def missing() -> str:
        raise LookupError

    with pytest.raises(LookupError):
        ctx.once("row", missing)

    assert ctx.once("row", lambda: "found") == "found"
