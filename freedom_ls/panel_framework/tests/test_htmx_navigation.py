"""Tests for HTMX navigation with OOB fragment responses."""

from __future__ import annotations

import pytest

from django.db.models import QuerySet
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.views import ListViewConfig, panel_framework_view

from .conftest import StubModel, make_staff_user


class StubDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet[StubModel]:
        qs: QuerySet[StubModel] = StubModel.objects.all()
        return qs

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Name",
                "template": "cotton/data-table-cells/text.html",
                "attr": "name",
            },
        ]


class StubListConfig(ListViewConfig):
    url_name = "stubs"
    menu_label = "Stubs"
    model = StubModel
    list_view = StubDataTable


CONFIG: dict[str, type[ListViewConfig]] = {
    "stubs": StubListConfig,
}

URL_NAME = "panel_framework_test:interface"
TEMPLATE = "panel_framework/test_interface.html"


def _make_request(
    path: str = "/test-panel/stubs",
    is_htmx: bool = False,
    hx_target: str = "",
) -> HttpRequest:
    """Build a GET request with optional HTMX headers."""
    factory = RequestFactory()
    kwargs: dict[str, str] = {}
    if is_htmx:
        kwargs["HTTP_HX_REQUEST"] = "true"
    if hx_target:
        kwargs["HTTP_HX_TARGET"] = hx_target
    request = factory.get(path, **kwargs)
    request.user = make_staff_user()
    return request


@pytest.mark.django_db
class TestHtmxNavigation:
    def test_non_htmx_returns_full_page(self, mock_site_context: None) -> None:
        """Non-HTMX request renders the full page template with breadcrumb content."""
        request = _make_request(is_htmx=False)
        response = panel_framework_view(
            config=CONFIG,
            request=request,
            path_string="stubs",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        # Breadcrumbs should contain the current-page label, not just an empty nav.
        assert 'aria-label="Breadcrumb"' in content
        assert 'aria-current="page"' in content
        assert "Stubs" in content

    def test_htmx_navigation_returns_oob_fragments(
        self, mock_site_context: None
    ) -> None:
        """HTMX request with HX-Target=main-content returns content + OOB fragments."""
        request = _make_request(is_htmx=True, hx_target="main-content")
        response = panel_framework_view(
            config=CONFIG,
            request=request,
            path_string="stubs",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Should contain main content div
        assert 'id="main-content"' in content
        # Should contain OOB sidebar
        assert 'id="sidebar-nav"' in content
        assert 'hx-swap-oob="true"' in content
        # Should contain OOB breadcrumbs
        assert 'id="breadcrumbs"' in content

    def test_htmx_non_navigation_returns_fragment_only(
        self, mock_site_context: None
    ) -> None:
        """HTMX request without HX-Target=main-content returns only the content fragment."""
        request = _make_request(is_htmx=True, hx_target="some-other-target")
        response = panel_framework_view(
            config=CONFIG,
            request=request,
            path_string="stubs",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        assert response.status_code == 200
        content = response.content.decode()
        # Should NOT contain OOB attributes or navigation elements
        assert 'hx-swap-oob="true"' not in content
        assert 'id="sidebar-nav"' not in content
        assert 'id="main-content"' not in content

    def test_htmx_navigation_main_content_div_present(
        self, mock_site_context: None
    ) -> None:
        """HTMX navigation response wraps content in div with id=main-content."""
        request = _make_request(is_htmx=True, hx_target="main-content")
        response = panel_framework_view(
            config=CONFIG,
            request=request,
            path_string="stubs",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        content = response.content.decode()
        assert '<div id="main-content" class="space-y-4 pl-2 sm:pl-6">' in content

    def test_htmx_navigation_includes_heading(self, mock_site_context: None) -> None:
        """HTMX navigation response includes heading from menu_label."""
        request = _make_request(is_htmx=True, hx_target="main-content")
        response = panel_framework_view(
            config=CONFIG,
            request=request,
            path_string="stubs",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        content = response.content.decode()
        assert "<h1>Stubs</h1>" in content
