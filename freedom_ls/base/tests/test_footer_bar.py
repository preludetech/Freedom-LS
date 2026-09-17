"""Tests for the site footer: `partials/footer_bar.html` and the `{% block footer %}`
site it fills in `_base.html`.

Rendered straight from the shell templates with a `RequestFactory` request, the same
way `test_head_metadata.py` exercises `_base.html` itself rather than any one page
that extends it.
"""

from __future__ import annotations

import datetime
import re

import pytest

from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse


def _render(template_name: str = "_base.html", **context: str) -> str:
    """Render `template_name` for a GET of `/` and return the markup."""
    request = RequestFactory().get("/")
    return render_to_string(template_name, context, request=request)


ERROR_TEMPLATES = ["400.html", "403.html", "403_csrf.html", "404.html", "429.html"]


@pytest.mark.django_db
def test_footer_is_a_sibling_of_main_not_nested_inside_it(mock_site_context):
    """A <footer> nested inside <main> loses the contentinfo landmark silently,
    so the placement itself — not merely the element's presence — is the thing
    under test."""
    body = _render()
    main_close = body.index("</main>")
    footer_open = body.index("<footer")
    assert footer_open > main_close


@pytest.mark.django_db
def test_base_html_renders_exactly_one_footer_element(mock_site_context):
    body = _render()
    assert body.count("<footer") == 1


@pytest.mark.django_db
def test_no_explicit_contentinfo_role_is_present(mock_site_context):
    """The implicit role from <footer> is sufficient; an explicit one is redundant."""
    body = _render()
    assert 'role="contentinfo"' not in body


@pytest.mark.django_db
def test_copyright_line_carries_the_current_year_and_header_title(mock_site_context):
    """`header_title` is driven by a global setting, not by the site fixture, so
    it is supplied explicitly here rather than read off `mock_site_context`."""
    body = _render(header_title="Freedom Academy")
    year = datetime.datetime.now(tz=datetime.UTC).year
    assert f"&copy; {year} Freedom Academy" in body


@pytest.mark.django_db
def test_terms_link_points_at_the_legal_doc_url(mock_site_context):
    body = _render()
    url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    assert f'href="{url}"' in body


@pytest.mark.django_db
def test_privacy_link_points_at_the_legal_doc_url(mock_site_context):
    body = _render()
    url = reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    assert f'href="{url}"' in body


@pytest.mark.django_db
def test_terms_link_text_matches_the_signup_consent_link(mock_site_context):
    body = _render()
    assert "Terms and Conditions" in body


@pytest.mark.django_db
def test_privacy_link_text_matches_the_signup_consent_link(mock_site_context):
    body = _render()
    assert "Privacy Policy" in body


@pytest.mark.django_db
def test_terms_link_precedes_privacy_link_in_full_footer(mock_site_context):
    body = _render()
    terms_url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    privacy_url = reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    assert body.index(terms_url) < body.index(privacy_url)


@pytest.mark.django_db
def test_terms_link_precedes_privacy_link_in_compact_footer(mock_site_context):
    body = _render("_base_interface.html")
    terms_url = reverse("accounts:legal_doc", kwargs={"doc_type": "terms"})
    privacy_url = reverse("accounts:legal_doc", kwargs={"doc_type": "privacy"})
    assert body.index(terms_url) < body.index(privacy_url)


@pytest.mark.django_db
def test_footer_nav_carries_legal_aria_label(mock_site_context):
    body = _render()
    match = re.search(r"<footer.*?</footer>", body, re.DOTALL)
    assert match is not None
    assert '<nav aria-label="Legal"' in match.group(0)


@pytest.mark.django_db
def test_base_interface_renders_exactly_one_footer_after_main(mock_site_context):
    body = _render("_base_interface.html")
    main_close = body.index("</main>")
    footer_open = body.index("<footer")
    assert footer_open > main_close
    assert body.count("<footer") == 1


@pytest.mark.django_db
def test_base_interface_footer_is_compact(mock_site_context):
    body = _render("_base_interface.html")
    assert 'data-compact="true"' in body


@pytest.mark.django_db
def test_base_html_footer_is_not_compact(mock_site_context):
    body = _render()
    assert 'data-compact="false"' in body


@pytest.mark.django_db
def test_exam_runner_base_renders_no_footer(mock_site_context):
    body = _render("learner_interface/_exam_runner_base.html")
    assert "<footer" not in body


@pytest.mark.django_db
@pytest.mark.parametrize("template_name", ERROR_TEMPLATES)
def test_error_page_renders_no_footer(mock_site_context, template_name: str):
    request = RequestFactory().get("/no-such-page/")
    body = render_to_string(template_name, request=request)
    assert "<footer" not in body


@pytest.mark.django_db
def test_body_is_a_sticky_footer_shell(mock_site_context):
    """On a page shorter than the viewport the footer must sit at the bottom of
    the screen, not stranded above a band of bare background."""
    body = _render()
    body_classes = re.search(r'<body class="([^"]*)"', body)
    main_classes = re.search(r'<main class="([^"]*)"', body)
    assert body_classes is not None
    assert main_classes is not None
    assert {"min-h-dvh", "flex", "flex-col"} <= set(body_classes.group(1).split())
    assert "grow" in main_classes.group(1).split()


@pytest.mark.django_db
def test_debug_badge_reserves_room_below_the_footer_on_narrow_screens(
    mock_site_context,
):
    """The fixed debug badge sits in the bottom-left corner, where the footer's
    copyright line lands on a narrow screen."""
    body = _render(debug_branch_name="my-feature")
    style = re.search(
        r"@media \(max-width: 479px\) \{(.*?)\n\s*\}\s*</style>", body, re.DOTALL
    )
    assert style is not None
    assert re.search(r"body > footer \{[^}]*padding-bottom", style.group(1))
