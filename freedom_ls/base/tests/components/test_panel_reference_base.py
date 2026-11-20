"""FLS's override of the reference page's base template wins by path and fills
both blocks the page defines."""

from __future__ import annotations

import re

import pytest

from django.template.loader import render_to_string
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


def _render() -> str:
    request = RequestFactory().get("/panel-framework/components/")
    return render_to_string(
        "panel_framework/reference/component_reference.html", request=request
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
