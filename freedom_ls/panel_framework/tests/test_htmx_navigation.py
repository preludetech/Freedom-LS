"""Response branches: full page, navigation bundle, tab and region fragments."""

from __future__ import annotations

import pytest

from .conftest import _make_stub
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db

LIST_REGION_ID = "panel-test-panel-framework-stubs"
VARY_HEADERS = ("HX-Request", "HX-Target", "HX-History-Restore-Request")


class TestFullPage:
    def test_non_htmx_returns_full_page(self, mock_site_context) -> None:
        response = fetch("stubs")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        assert 'aria-label="Breadcrumb"' in content
        assert 'aria-current="page"' in content
        assert "Stubs" in content

    def test_a_history_restore_of_an_instance_url_returns_the_full_page(
        self, mock_site_context
    ) -> None:
        stub = _make_stub(name="Restored Stub")

        response = fetch(f"stubs/{stub.pk}", htmx=True, restore=True)

        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        assert "Restored Stub" in content


class TestNavigationResponse:
    def test_htmx_navigation_returns_oob_fragments(self, mock_site_context) -> None:
        response = fetch("stubs", htmx=True, hx_target="main-content")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="main-content"' in content
        assert 'id="sidebar-nav"' in content
        assert 'hx-swap-oob="true"' in content
        assert 'id="breadcrumbs"' in content
        assert "Stubs" in content

    def test_an_unknown_target_gets_the_navigation_response_not_a_fragment(
        self, mock_site_context
    ) -> None:
        response = fetch("stubs", htmx=True, hx_target="some-other-target")

        content = response.content.decode()
        assert 'id="main-content"' in content
        assert 'id="sidebar-nav"' in content

    def test_an_htmx_request_with_no_target_gets_the_navigation_response(
        self, mock_site_context
    ) -> None:
        response = fetch("stubs", htmx=True)

        assert 'id="main-content"' in response.content.decode()

    def test_htmx_navigation_includes_heading(self, mock_site_context) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert 'id="page-title"' in content
        assert "Stubs" in content

    def test_htmx_navigation_includes_announcer_when_set(
        self, mock_site_context
    ) -> None:
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_announcement = "Now viewing Acme"

        content = call_view(request, "stubs").content.decode()

        assert 'hx-swap-oob="innerHTML:#scope-announcer"' in content
        assert "Now viewing Acme" in content

    def test_announcer_fragment_never_carries_the_live_regions_own_id(
        self, mock_site_context
    ) -> None:
        """The fragment must update the live region's contents, never replace
        the region itself: a torn-down-and-rebuilt live region goes
        unannounced by some screen readers."""
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_announcement = "Now viewing Acme"

        content = call_view(request, "stubs").content.decode()

        assert 'id="scope-announcer"' not in content

    def test_htmx_navigation_omits_announcer_when_unset(
        self, mock_site_context
    ) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert "scope-announcer" not in content

    def test_htmx_navigation_includes_every_extra_oob_fragment(
        self, mock_site_context
    ) -> None:
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_extra_oob = [
            "panel_framework/test_extra_oob_fragment.html",
            "panel_framework/test_second_extra_oob_fragment.html",
        ]

        content = call_view(request, "stubs").content.decode()

        assert 'id="test-extra-oob-fragment" hx-swap-oob="true"' in content
        assert "extra fragment content" in content
        assert 'id="test-second-extra-oob-fragment" hx-swap-oob="true"' in content

    def test_htmx_navigation_omits_extra_oob_fragments_when_unset(
        self, mock_site_context
    ) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert 'id="test-extra-oob-fragment"' not in content

    def test_htmx_navigation_threads_extra_url_kwargs_into_reversed_urls(
        self, mock_site_context
    ) -> None:
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_url_kwargs = {"extra": "acme"}

        response = call_view(
            request, "stubs", url_name="panel_framework_test:scoped_interface"
        )

        assert "/test-panel/scoped/acme/stubs" in response.content.decode()


class TestRegionResponse:
    def test_a_request_targeting_the_list_region_returns_only_the_table(
        self, mock_site_context
    ) -> None:
        _make_stub(name="row-1")

        content = fetch("stubs", htmx=True, hx_target=LIST_REGION_ID).content.decode()

        assert f'id="{LIST_REGION_ID}"' in content
        assert "row-1" in content
        assert "<section" not in content
        assert "Create Item" not in content
        assert 'id="sidebar-nav"' not in content


class TestVary:
    @pytest.mark.parametrize(
        "request_kwargs",
        [
            {},
            {"htmx": True, "hx_target": LIST_REGION_ID},
            {"htmx": True, "hx_target": "main-content"},
        ],
        ids=["plain", "region fragment", "navigation"],
    )
    def test_every_branch_of_one_url_varies_on_the_htmx_headers(
        self, mock_site_context, request_kwargs
    ) -> None:
        response = fetch("stubs", **request_kwargs)

        for header in VARY_HEADERS:
            assert header in response["Vary"]

    def test_an_action_422_varies_on_the_htmx_headers(self, mock_site_context) -> None:
        _make_stub(name="Taken")
        response = fetch(
            "stubs/__actions/create_item", method="post", data={"name": "Taken"}
        )

        assert response.status_code == 422
        for header in VARY_HEADERS:
            assert header in response["Vary"]
