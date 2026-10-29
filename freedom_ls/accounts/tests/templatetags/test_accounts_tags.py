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


@pytest.mark.parametrize(
    ("next_value", "expected"),
    [
        (
            "/applications/apply/x/",
            # The tag's return value is autoescaped like any other rendered
            # output, so a real caller reads this the same way a browser
            # does: as one `&`-joined query string.
            "/accounts/signup/?next=%2Fapplications%2Fapply%2Fx%2F&amp;email=a%40b.example",
        ),
        (None, "/accounts/signup/?email=a%40b.example"),
    ],
)
def test_url_with_next_also_carries_an_extra_query_kwarg(rf, next_value, expected):
    params = {"next": next_value} if next_value is not None else {}
    request = rf.get("/accounts/signup/", params)
    template = Template(
        '{% load accounts_tags %}{% url_with_next "account_signup" email="a@b.example" %}'
    )

    with request_context(request):
        rendered = template.render(Context({"request": request}))

    assert rendered == expected


def test_url_with_next_drops_an_empty_extra_kwarg(rf):
    request = rf.get("/accounts/signup/")
    template = Template(
        '{% load accounts_tags %}{% url_with_next "account_signup" email="" %}'
    )

    with request_context(request):
        rendered = template.render(Context({"request": request}))

    assert rendered == "/accounts/signup/"


def test_url_with_next_reads_next_from_the_post_body(rf):
    request = rf.post("/accounts/login/", {"next": "/applications/apply/x/"})
    template = Template(
        '{% load accounts_tags %}{% url_with_next "account_signup" email="a@b.example" %}'
    )

    with request_context(request):
        rendered = template.render(Context({"request": request}))

    assert rendered == (
        "/accounts/signup/?next=%2Fapplications%2Fapply%2Fx%2F&amp;email=a%40b.example"
    )


def _render_url_back_here(request, **context: object) -> str:
    template = Template('{% load accounts_tags %}{% url_back_here "account_login" %}')
    with request_context(request):
        return template.render(Context({"request": request, **context}))


def test_url_back_here_carries_the_current_path_as_next(rf):
    request = rf.get("/courses/intro/detail/")

    rendered = _render_url_back_here(request)

    assert rendered == "/accounts/login/?next=%2Fcourses%2Fintro%2Fdetail%2F"


def test_url_back_here_url_encodes_the_query_string_into_next(rf):
    request = rf.get("/courses/intro/detail/", {"page": "2"})

    rendered = _render_url_back_here(request)

    assert rendered == (
        "/accounts/login/?next=%2Fcourses%2Fintro%2Fdetail%2F%3Fpage%3D2"
    )


@pytest.mark.parametrize(
    "path",
    ["/", "/accounts/login/", "/applications/claim/some-token/"],
    ids=["home", "account_page", "claim_page"],
)
def test_url_back_here_is_bare_where_returning_makes_no_sense(rf, path):
    request = rf.get(path)

    rendered = _render_url_back_here(request)

    assert rendered == "/accounts/login/"


def test_url_back_here_is_bare_on_an_error_page(rf):
    request = rf.get("/courses/missing/detail/")

    rendered = _render_url_back_here(request, is_error_page=True)

    assert rendered == "/accounts/login/"


def test_url_back_here_is_bare_for_a_post_request(rf):
    request = rf.post("/courses/intro/detail/")

    rendered = _render_url_back_here(request)

    assert rendered == "/accounts/login/"


def test_url_back_here_passes_a_request_next_through_unchanged(rf):
    request = rf.get("/courses/intro/detail/", {"next": "/x/"})

    rendered = _render_url_back_here(request)

    assert rendered == "/accounts/login/?next=%2Fx%2F"


def test_url_back_here_is_bare_with_no_request_in_context():
    template = Template('{% load accounts_tags %}{% url_back_here "account_login" %}')

    rendered = template.render(Context({}))

    assert rendered == "/accounts/login/"
