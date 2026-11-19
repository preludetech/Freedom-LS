"""FLS's base for the component reference page fills both blocks the page defines."""

from __future__ import annotations

import re

import pytest

from django.template.loader import render_to_string
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


def _render() -> str:
    request = RequestFactory().get("/panel-framework/components/")
    context = {"reference_base_template": "panel_reference_base.html"}
    return render_to_string(
        "panel_framework/reference/component_reference.html", context, request=request
    )


def test_the_reference_page_fills_the_title_and_content_blocks(
    mock_site_context: object,
) -> None:
    html = _render()

    title = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    assert title is not None
    assert "Component reference" in title.group(1)
    assert 'id="table-default"' in html


def test_the_reference_page_loads_the_panel_framework_alpine_components(
    mock_site_context: object,
) -> None:
    assert "panel_framework/js/alpine-components.js" in _render()
