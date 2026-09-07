"""Tests for the head metadata blocks in `_base.html`.

Covers the canonical link, the robots directive and the Open Graph / Twitter
card tags, plus their defaults. These are rendered straight from `_base.html`
with a `RequestFactory` request so the assertions are about the base template
itself rather than any one page that extends it.
"""

from __future__ import annotations

import re

import pytest

from django.template.loader import render_to_string
from django.test import RequestFactory

GENERIC_DESCRIPTION = "Learning management system"


def _render(
    path: str = "/", query: dict[str, str] | None = None, **context: str
) -> str:
    """Render `_base.html` for a GET of `path` and return the markup."""
    request = RequestFactory().get(path, query or {})
    return render_to_string("_base.html", context, request=request)


def _canonical(body: str) -> str | None:
    match = re.search(r'<link rel="canonical" href="([^"]*)"', body)
    return match.group(1) if match else None


def _meta_property(body: str, name: str) -> str:
    """Content of a <meta property="..."> tag, whichever order the attributes are in."""
    match = re.search(rf'<meta property="{re.escape(name)}"\s+content="([^"]*)"', body)
    if not match:
        match = re.search(
            rf'<meta content="([^"]*)"\s+property="{re.escape(name)}"', body
        )
    assert match, f"no <meta property='{name}'> tag found"
    return match.group(1)


def _meta_name(body: str, name: str) -> str:
    match = re.search(rf'<meta name="{re.escape(name)}"\s+content="([^"]*)"', body)
    if not match:
        match = re.search(rf'<meta content="([^"]*)"\s+name="{re.escape(name)}"', body)
    assert match, f"no <meta name='{name}'> tag found"
    return match.group(1)


@pytest.mark.django_db
def test_canonical_link_strips_the_query_string(mock_site_context):
    """The same page behind different utm_* strings canonicalises to one URL."""
    body = _render("/courses/", {"utm_source": "newsletter", "utm_medium": "email"})
    assert _canonical(body) == "http://testserver/courses/"


@pytest.mark.django_db
def test_og_url_matches_the_canonical_link(mock_site_context):
    body = _render("/courses/", {"utm_campaign": "spring"})
    assert _meta_property(body, "og:url") == _canonical(body)


@pytest.mark.django_db
def test_robots_defaults_to_index_follow(mock_site_context):
    assert _meta_name(_render(), "robots") == "index, follow"


@pytest.mark.django_db
def test_social_meta_defaults(mock_site_context):
    body = _render()
    assert _meta_property(body, "og:type") == "website"
    assert _meta_property(body, "og:site_name") == mock_site_context.name
    assert _meta_property(body, "og:title") == mock_site_context.name
    assert _meta_name(body, "twitter:card") == "summary"


@pytest.mark.django_db
def test_descriptions_use_the_view_supplied_meta_description(mock_site_context):
    """One `meta_description` context value drives both descriptions."""
    body = _render(meta_description="A thorough introduction to Python.")
    assert _meta_name(body, "description") == "A thorough introduction to Python."
    assert (
        _meta_property(body, "og:description") == "A thorough introduction to Python."
    )


@pytest.mark.django_db
def test_og_description_falls_back_to_the_generic_default(mock_site_context):
    assert _meta_property(_render(), "og:description") == GENERIC_DESCRIPTION


@pytest.mark.django_db
def test_no_canonical_link_is_emitted_without_a_request(mock_site_context):
    """Rendering with no request must not emit an empty canonical URL."""
    body = render_to_string("_base.html")
    assert _canonical(body) is None
    assert "og:url" not in body


@pytest.mark.django_db
def test_error_page_emits_exactly_one_noindex_robots_tag(mock_site_context):
    """The 404 replaces head_seo rather than adding a second tag via extra_head."""
    request = RequestFactory().get("/no-such-page/")
    body = render_to_string("404.html", request=request)
    assert body.count('name="robots"') == 1
    assert _meta_name(body, "robots") == "noindex"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "template_name", ["400.html", "403.html", "403_csrf.html", "404.html", "429.html"]
)
def test_error_pages_emit_no_canonical_or_social_tags(
    mock_site_context, template_name: str
):
    """Canonical and og:url both echo the request path.

    `test_no_page_echoes_its_own_trigger_path` in test_error_pages.py holds the
    rule; this pins the head_seo override that keeps it true.
    """
    request = RequestFactory().get("/no-such-page/")
    body = render_to_string(template_name, request=request)
    assert _canonical(body) is None
    assert "og:" not in body
    assert "twitter:" not in body


@pytest.mark.django_db
def test_lockout_page_is_noindex_via_the_robots_block(mock_site_context):
    """A real page that should not be indexed keeps its canonical link."""
    request = RequestFactory().get("/accounts/login/")
    body = render_to_string("accounts/lockout.html", request=request)
    assert _meta_name(body, "robots") == "noindex"
    assert _canonical(body) == "http://testserver/accounts/login/"
