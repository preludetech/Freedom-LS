"""Tests for the <c-section-pagination /> cotton component."""

from __future__ import annotations

import re

from django_cotton.compiler_regex import CottonCompiler

from django.core.paginator import Paginator
from django.template import Context, Template
from django.test import RequestFactory

_cotton_compiler = CottonCompiler()

_TEMPLATE = (
    '<c-section-pagination :page_obj="page_obj" target_id="swap-x" '
    'page_param_name="page_x" nav_label="Things pages" />'
)


def _render(
    query: dict[str, str] | None = None, source: str = _TEMPLATE, page: int = 1
) -> str:
    request = RequestFactory().get("/dashboard/", query or {})
    page_obj = Paginator(list(range(7)), 3).page(page)
    template = Template(_cotton_compiler.process(source))
    return template.render(Context({"request": request, "page_obj": page_obj}))


def _control(html: str, direction: str) -> str:
    match = re.search(rf'<a [^>]*data-direction="{direction}"[^>]*>', html)
    assert match, f"no {direction} control in {html}"
    return match.group(0)


def test_both_controls_render():
    html = _render()

    assert 'data-direction="previous"' in html
    assert 'data-direction="next"' in html


def test_the_boundary_control_is_aria_disabled_not_disabled():
    previous = _control(_render(), "previous")

    assert 'aria-disabled="true"' in previous
    assert 'tabindex="-1"' in previous
    assert "disabled" not in previous.replace('aria-disabled="true"', "")
    assert "href=" not in previous


def test_the_next_control_carries_matching_href_and_hx_get():
    next_control = _control(_render(), "next")

    assert 'href="/dashboard/?page_x=2"' in next_control
    assert 'hx-get="/dashboard/?page_x=2"' in next_control
    assert 'hx-target="#swap-x"' in next_control
    assert 'hx-swap="outerHTML"' in next_control
    assert "hx-select" not in next_control


def test_a_reflected_query_value_is_encoded_never_raw():
    html = _render({"utm": 'a"<b'})

    next_control = _control(html, "next")
    assert "utm=a%22%3Cb" in next_control
    assert 'a"<b' not in next_control
    assert "a<b" not in next_control


def test_the_next_control_replaces_the_url():
    assert 'hx-replace-url="true"' in _control(_render(), "next")


def test_the_previous_control_replaces_the_url():
    assert 'hx-replace-url="true"' in _control(_render(page=2), "previous")


def test_the_disabled_previous_control_has_no_hx_replace_url():
    assert "hx-replace-url" not in _control(_render(), "previous")


def test_the_disabled_next_control_has_no_hx_replace_url():
    assert "hx-replace-url" not in _control(_render(page=3), "next")
