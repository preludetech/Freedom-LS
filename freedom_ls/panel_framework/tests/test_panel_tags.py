"""Tests for the panel_tags template tags."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from django.template import Context, RequestContext, Template
from django.test import RequestFactory

from freedom_ls.panel_framework.actions import PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.templatetags.panel_tags import (
    avatar_slot,
    clamp_percentage,
    heading_level,
    initials,
    tone,
)

from .conftest import _make_stub
from .stub_panels import StubDetailsPanel


class _LinkAction(PanelAction):
    """Renders through a test template that prints the action URL."""

    action_name = "go"
    template_name = "panel_framework/test_action_url.html"


@pytest.mark.django_db
def test_resolve_url_path_template_builds_url_from_object_attrs(
    mock_site_context: None,
) -> None:
    """Placeholders in the path template are substituted from object attributes."""
    request = RequestFactory().get("/whatever")
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:interface' 'cohorts/{pk}' %}"
    )
    result = template.render(RequestContext(request, {"obj": obj}))
    assert result.strip() == "/test-panel/cohorts/42"


@pytest.mark.django_db
def test_resolve_url_path_template_merges_panel_url_kwargs(
    mock_site_context: None,
) -> None:
    """request.panel_url_kwargs reaches this tag's reverse() call, same as the sidebar/breadcrumb builders."""
    request = RequestFactory().get("/whatever")
    request.panel_url_kwargs = {"extra": "acme"}
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:scoped_interface' 'cohorts/{pk}' %}"
    )
    result = template.render(RequestContext(request, {"obj": obj}))
    assert result.strip() == "/test-panel/scoped/acme/cohorts/42"


@pytest.mark.django_db
def test_resolve_url_path_template_without_a_request_in_the_context(
    mock_site_context: None,
) -> None:
    """Rendered outside a request, the tag falls back to no extra kwargs
    rather than raising on the missing 'request' context variable."""
    obj = SimpleNamespace(pk=42)
    template = Template(
        "{% load panel_tags %}"
        "{% resolve_url_path_template obj 'panel_framework_test:interface' 'cohorts/{pk}' %}"
    )
    result = template.render(Context({"obj": obj}))
    assert result.strip() == "/test-panel/cohorts/42"


@pytest.mark.django_db
def test_render_panel_renders_the_panels_template_with_its_context(
    mock_site_context: None,
) -> None:
    stub = _make_stub(name="Tagged Stub")
    panel = StubDetailsPanel(
        PanelContext(
            request=RequestFactory().get("/"),
            instance=stub,
            base_url="/stubs/1",
            name="details",
        )
    )
    template = Template("{% load panel_tags %}{% render_panel panel %}")

    result = template.render(Context({"panel": panel}))

    assert "<p data-stub-details>Tagged Stub</p>" in result
    assert 'data-panel="details"' in result


@pytest.mark.django_db
def test_render_action_builds_the_action_url_from_the_context(
    mock_site_context: None,
) -> None:
    ctx = PanelContext(
        request=RequestFactory().get("/"), instance=None, base_url="/a/b", name=""
    )
    template = Template("{% load panel_tags %}{% render_action action ctx %}")

    result = template.render(Context({"action": _LinkAction(), "ctx": ctx}))

    assert 'data-url="/a/b/__actions/go"' in result


@pytest.mark.parametrize("value", ["success", "warning", "error", "info", "muted"])
def test_tone_passes_through_a_known_tone(value: str) -> None:
    assert tone(value) == value


@pytest.mark.parametrize("value", ["primary", "secondary", "unknown", ""])
def test_tone_falls_back_to_muted_for_anything_else(value: str) -> None:
    assert tone(value) == "muted"


@pytest.mark.parametrize("value", ["1", "2", "3", "4", "5", "6"])
def test_heading_level_passes_through_a_known_level(value: str) -> None:
    assert heading_level(value, "1") == value


@pytest.mark.parametrize("value", ["0", "7", "abc", ""])
def test_heading_level_falls_back_to_the_default_for_anything_else(
    value: str,
) -> None:
    assert heading_level(value, "2") == "2"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-5, 0), (150, 100), ("72", 72), (72.6, 72)],
)
def test_clamp_percentage_clamps_to_0_100(
    value: int | float | str, expected: int
) -> None:
    assert clamp_percentage(value) == expected


def test_avatar_slot_is_within_1_to_6() -> None:
    for value in range(20):
        assert 1 <= avatar_slot(value) <= 6


def test_avatar_slot_is_the_same_for_an_int_and_its_string() -> None:
    assert avatar_slot(42) == avatar_slot("42")


def test_avatar_slot_is_stable_across_repeated_calls() -> None:
    assert avatar_slot(42) == avatar_slot(42)


def test_avatar_slot_is_stable_for_a_uuid() -> None:
    value = uuid.uuid4()

    assert avatar_slot(value) == avatar_slot(value)


def test_avatar_slot_spreads_across_more_than_one_slot() -> None:
    slots = {avatar_slot(user_id) for user_id in range(20)}

    assert len(slots) > 1


@pytest.mark.parametrize(
    ("name", "expected"),
    [("Thandi Mokoena", "TM"), ("Cher", "C"), ("", "")],
)
def test_initials_derives_from_the_first_and_last_words(
    name: str, expected: str
) -> None:
    assert initials(name) == expected
