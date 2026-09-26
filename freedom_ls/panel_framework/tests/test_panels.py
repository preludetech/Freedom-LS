"""Bound panels: binding, visibility, children and region ids."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.db.models import QuerySet
from django.http import Http404, HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import Panel, PanelStack, TabSet

from .conftest import StubModel, _make_stub
from .stub_panels import StubDataTablePanel, StubDetailsPanel, StubHiddenPanel


class _Stack(PanelStack):
    children = {"shown": StubDataTablePanel, "hidden": StubHiddenPanel}


class _AllHiddenTabs(TabSet):
    children = {"one": StubHiddenPanel, "two": StubHiddenPanel}


class _Tabs(TabSet):
    children = {"details": StubDataTablePanel, "details2": StubDataTablePanel}


class _ModelPanel(Panel):
    model = StubModel


class _NarrowedTablePanel(StubDataTablePanel):
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(name__startswith="keep")


def _ctx(path: str = "/base", instance: StubModel | None = None) -> PanelContext:
    return PanelContext(
        request=RequestFactory().get(path),
        instance=instance,
        base_url="/base",
        name="",
    )


def test_a_hidden_child_is_left_out_of_get_children() -> None:
    stack = _Stack(_ctx())

    assert [child.ctx.name for child in stack.get_children()] == ["shown"]


def test_a_hidden_childs_name_is_a_404() -> None:
    stack = _Stack(_ctx())

    with pytest.raises(Http404):
        stack.child("hidden")


def test_a_container_whose_children_are_all_hidden_is_hidden() -> None:
    assert _AllHiddenTabs(_ctx()).is_shown() is False


def test_a_container_with_a_shown_child_is_shown() -> None:
    assert _Stack(_ctx()).is_shown() is True


def test_children_get_their_own_url_and_name() -> None:
    (child,) = _Stack(_ctx()).get_children()

    assert child.ctx.base_url == "/base/__panels/shown"
    assert child.ctx.name == "shown"


def test_two_children_get_different_region_ids() -> None:
    first, second = _Tabs(_ctx()).get_children()

    assert first.region_id != second.region_id


def test_tab_set_reads_its_active_child_from_the_request_path() -> None:
    tabs = _Tabs(_ctx("/base/__tabs/details2"))

    assert tabs.get_active_child().ctx.name == "details2"


def test_a_tab_does_not_claim_a_longer_tab_name_that_starts_with_it() -> None:
    tabs = _Tabs(_ctx("/base/__tabs/details2/__panels/x"))

    assert tabs.get_active_child().ctx.name == "details2"


def test_tab_set_falls_back_to_its_first_shown_child() -> None:
    tabs = _Tabs(_ctx("/base"))

    assert tabs.get_active_child().ctx.name == "details"


def test_a_panel_declaring_a_model_refuses_to_bind_without_an_instance() -> None:
    with pytest.raises(ImproperlyConfigured):
        _ModelPanel(_ctx())


def test_a_panel_without_a_model_binds_without_an_instance() -> None:
    assert StubDetailsPanel(_ctx()).instance is None


@pytest.mark.django_db
def test_a_get_queryset_override_narrows_the_rows(mock_site_context: Site) -> None:
    _make_stub(name="keep-me")
    _make_stub(name="drop-me")

    context = _NarrowedTablePanel(_ctx()).get_context_data()

    assert [row.name for row in context["rows"]] == ["keep-me"]
