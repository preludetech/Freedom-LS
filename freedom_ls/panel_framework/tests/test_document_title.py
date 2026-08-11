"""The HTMX navigation bundle carries a browser-tab <title>.

Navigation never reloads the page, so without a <title> in the fragment the tab
would keep whatever the last full page load put there. htmx lifts a root-level
<title> out of a partial response and applies it to document.title.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.views import ListViewConfig, panel_framework_view

from .conftest import make_staff_user
from .stub_panels import StubListConfig

CONFIG: dict[str, type[ListViewConfig]] = {
    "stubs": StubListConfig,
}

URL_NAME = "panel_framework_test:interface"
TEMPLATE = "panel_framework/test_interface.html"


def _navigation_request() -> HttpRequest:
    """A GET that looks like an in-interface HTMX navigation."""
    request = RequestFactory().get(
        "/test-panel/stubs",
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="main-content",
    )
    request.user = make_staff_user()
    return request


def _navigate(request: HttpRequest) -> str:
    """Run a navigation and return the rendered OOB bundle."""
    response = panel_framework_view(
        config=CONFIG,
        request=request,
        path_string="stubs",
        template_name=TEMPLATE,
        url_name=URL_NAME,
    )
    return response.content.decode()


def _title_text(html: str) -> str:
    """The text inside the response's <title> element, whitespace stripped."""
    return html.split("<title>")[1].split("</title>")[0].strip()


@pytest.mark.django_db
def test_navigation_bundle_names_the_page_and_the_site(
    mock_site_context: Site,
) -> None:
    """A host with no organisation concept gets no empty segment or stray dash."""
    content = _navigate(_navigation_request())

    assert _title_text(content) == f"Stubs — {mock_site_context.name}"


@pytest.mark.django_db
def test_navigation_title_names_the_organisation_the_request_carries(
    mock_site_context: Site,
) -> None:
    """panel_framework passes the fragment no context of its own, so the
    organisation segment is sourced from the request, as the announcer's
    message and the extra OOB fragments already are."""
    request = _navigation_request()
    request.organisation = SimpleNamespace(name="Northside Academy")

    content = _navigate(request)

    assert (
        _title_text(content) == f"Stubs — Northside Academy — {mock_site_context.name}"
    )
