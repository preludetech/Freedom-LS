"""Tests for the `accounts_tags` template tag library."""

from __future__ import annotations

import pytest
from allauth.core.context import request_context

from django.template import Context, Template


def _render_url_with_next(request) -> str:
    template = Template('{% load accounts_tags %}{% url_with_next "account_signup" %}')
    with request_context(request):
        return template.render(Context({"request": request}))


@pytest.mark.parametrize(
    ("next_value", "expected"),
    [
        (
            "/applications/apply/x/",
            "/accounts/signup/?next=%2Fapplications%2Fapply%2Fx%2F",
        ),
        (None, "/accounts/signup/"),
        ("https://evil.example.com/", "/accounts/signup/"),
    ],
)
def test_url_with_next_carries_only_a_safe_next(rf, next_value, expected):
    params = {"next": next_value} if next_value is not None else {}
    request = rf.get("/accounts/signup/", params)

    rendered = _render_url_with_next(request)

    assert rendered == expected


def test_url_with_next_falls_back_to_bare_url_with_no_request_in_context():
    template = Template('{% load accounts_tags %}{% url_with_next "account_signup" %}')

    rendered = template.render(Context({}))

    assert rendered == "/accounts/signup/"
