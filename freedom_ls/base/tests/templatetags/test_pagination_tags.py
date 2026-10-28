"""Tests for the pagination template tags."""

from __future__ import annotations

from django.template import Context, Template


def test_page_href_renders_the_path_with_the_requested_page(rf):
    request = rf.get("/dashboard/")
    template = Template('{% load pagination_tags %}{% page_href "page_x" 2 %}')

    rendered = template.render(Context({"request": request}))

    assert rendered == "/dashboard/?page_x=2"
