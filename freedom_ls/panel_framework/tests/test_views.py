"""Tests for the panel framework view: the response branches (full page,
navigation bundle, region fragments), the document title, list refresh wiring, access
checks and breadcrumbs."""

from __future__ import annotations

import re

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.test import RequestFactory

from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    NavGroup,
    ObjectViewConfig,
    _build_breadcrumbs,
    panel_framework_view,
)

from .helpers import make_staff_user, make_stub
from .stub_models import StubModel
from .stub_panels import StubDataTablePanel, StubDetailsPanel
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db


# Response branches: full page, navigation bundle, tab and region fragments.


LIST_REGION_ID = "stubs-table"
VARY_HEADERS = ("HX-Request", "HX-Target", "HX-History-Restore-Request")
INTERFACE_TEMPLATE = "panel_framework/test_interface.html"
INTERFACE_URL_NAME = "panel_framework_test:interface"


class TestFullPage:
    def test_non_htmx_returns_full_page(self, mock_site_context: Site) -> None:
        response = fetch("stubs")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        assert 'id="breadcrumbs"' in content
        assert 'aria-current="page"' in content
        assert "Stubs" in content

    def test_a_history_restore_of_an_instance_url_returns_the_full_page(
        self, mock_site_context: Site
    ) -> None:
        stub = make_stub(name="Restored Stub")

        response = fetch(f"stubs/{stub.pk}", htmx=True, restore=True)

        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        assert "Restored Stub" in content

    def test_the_modal_host_appears_exactly_once_on_the_full_page(
        self, mock_site_context: Site
    ) -> None:
        content = fetch("stubs").content.decode()

        assert content.count('id="app-modal"') == 1


class TestNavigationResponse:
    def test_htmx_navigation_returns_oob_fragments(
        self, mock_site_context: Site
    ) -> None:
        response = fetch("stubs", htmx=True, hx_target="main-content")

        assert response.status_code == 200
        content = response.content.decode()
        assert 'id="main-content"' in content
        assert 'id="sidebar-nav"' in content
        assert 'hx-swap-oob="true"' in content
        assert 'id="breadcrumbs"' in content
        assert "Stubs" in content

    def test_an_unknown_target_gets_the_navigation_response_not_a_fragment(
        self, mock_site_context: Site
    ) -> None:
        response = fetch("stubs", htmx=True, hx_target="some-other-target")

        content = response.content.decode()
        assert 'id="main-content"' in content
        assert 'id="sidebar-nav"' in content

    def test_an_htmx_request_with_no_target_gets_the_navigation_response(
        self, mock_site_context: Site
    ) -> None:
        response = fetch("stubs", htmx=True)

        assert 'id="main-content"' in response.content.decode()

    def test_htmx_navigation_includes_heading(self, mock_site_context: Site) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert 'id="page-title"' in content
        assert "Stubs" in content

    def test_htmx_navigation_includes_announcer_when_set(
        self, mock_site_context: Site
    ) -> None:
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_announcement = "Now viewing Acme"

        content = call_view(request, "stubs").content.decode()

        assert 'hx-swap-oob="innerHTML:#scope-announcer"' in content
        assert "Now viewing Acme" in content

    def test_announcer_fragment_never_carries_the_live_regions_own_id(
        self, mock_site_context: Site
    ) -> None:
        """The fragment must update the live region's contents, never replace
        the region itself: a torn-down-and-rebuilt live region goes
        unannounced by some screen readers."""
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_announcement = "Now viewing Acme"

        content = call_view(request, "stubs").content.decode()

        assert 'id="scope-announcer"' not in content

    def test_htmx_navigation_omits_announcer_when_unset(
        self, mock_site_context: Site
    ) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert "scope-announcer" not in content

    def test_htmx_navigation_includes_every_extra_oob_fragment(
        self, mock_site_context: Site
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
        self, mock_site_context: Site
    ) -> None:
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert 'id="test-extra-oob-fragment"' not in content

    def test_a_navigation_response_carries_no_modal_host(
        self, mock_site_context: Site
    ) -> None:
        """The modal host sits outside #main-content, so a navigation swap of
        #main-content never carries a second one onto the page."""
        content = fetch("stubs", htmx=True, hx_target="main-content").content.decode()

        assert 'id="app-modal"' not in content

    def test_htmx_navigation_threads_extra_url_kwargs_into_reversed_urls(
        self, mock_site_context: Site
    ) -> None:
        request = make_request("stubs", htmx=True, hx_target="main-content")
        request.panel_url_kwargs = {"extra": "acme"}

        response = call_view(
            request, "stubs", url_name="panel_framework_test:scoped_interface"
        )

        assert "/test-panel/scoped/acme/stubs" in response.content.decode()


class TestRegionResponse:
    def test_a_request_targeting_the_list_region_returns_only_the_table(
        self, mock_site_context: Site
    ) -> None:
        make_stub(name="row-1")

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
        self, mock_site_context: Site, request_kwargs: dict[str, object]
    ) -> None:
        response = fetch("stubs", **request_kwargs)

        for header in VARY_HEADERS:
            assert header in response["Vary"]

    def test_an_action_422_varies_on_the_htmx_headers(
        self, mock_site_context: Site
    ) -> None:
        make_stub(name="Taken")
        response = fetch(
            "stubs/__actions/create_item", method="post", data={"name": "Taken"}
        )

        assert response.status_code == 422
        for header in VARY_HEADERS:
            assert header in response["Vary"]


# The HTMX navigation bundle carries a browser-tab <title>.
#
# Navigation never reloads the page, so without a <title> in the fragment the tab
# would keep whatever the last full page load put there. htmx lifts a root-level
# <title> out of a partial response and applies it to document.title.


def _navigation_request() -> HttpRequest:
    """A GET that looks like an in-interface HTMX navigation."""
    return make_request("stubs", htmx=True, hx_target="main-content")


def _navigate(request: HttpRequest) -> str:
    """Run a navigation and return the rendered OOB bundle."""
    return call_view(request, "stubs").content.decode()


def _title_text(html: str) -> str:
    """The text inside the response's <title> element, whitespace stripped."""
    return html.split("<title>")[1].split("</title>")[0].strip()


@pytest.mark.django_db
def test_navigation_bundle_names_the_page_and_the_site(
    mock_site_context: Site,
) -> None:
    """A host that never sets panel_scope_name gets no empty segment or stray dash."""
    content = _navigate(_navigation_request())

    assert _title_text(content) == f"Stubs — {mock_site_context.name}"


@pytest.mark.django_db
def test_navigation_title_names_the_scope_the_request_carries(
    mock_site_context: Site,
) -> None:
    """panel_framework passes the fragment no context of its own, so the
    scope segment is sourced from the request, as the announcer's message and
    the extra OOB fragments already are."""
    request = _navigation_request()
    request.panel_scope_name = "Northside Academy"

    content = _navigate(request)

    assert (
        _title_text(content) == f"Stubs — Northside Academy — {mock_site_context.name}"
    )


# ListViewConfig.refresh_events refreshes the list's table region.


def test_the_refresh_wiring_targets_the_list_panels_region(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-2")

    html = fetch("stubs").content.decode()

    assert html.count('x-data="listRefresh"') == 1
    assert 'data-refresh-events="itemChanged"' in html
    assert f'data-refresh-target="{LIST_REGION_ID}"' in html
    assert f'id="{LIST_REGION_ID}"' in html


def test_a_region_refresh_skips_the_create_action(mock_site_context: Site) -> None:
    make_stub(name="row-1")

    html = fetch("stubs", htmx=True, hx_target=LIST_REGION_ID).content.decode()

    assert "row-1" in html
    assert "Create Item" not in html


def test_the_refresh_host_is_empty_and_the_create_action_sits_in_the_header(
    mock_site_context: Site,
) -> None:
    html = fetch("stubs").content.decode()

    refresh_host = re.search(
        r'<div x-data="listRefresh"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    assert refresh_host is not None
    assert refresh_host.group(1).strip() == ""
    assert "Create Item" in html


# Tests for ListViewConfig.check_access and authorise_instance.
#
# These exercise the mechanism directly, on hand-built requests, because the
# scope is deliberately opaque to the framework. The end-to-end coverage --
# every configured surface 404ing for a user with no access, through the real
# client -- lives in educator_interface/tests/test_config_authorisation.py.


class _StubInstanceView(InstanceView):
    panel = StubDetailsPanel


class DenyByDefaultConfig(ListViewConfig):
    """Defines model and instance_view but never overrides authorise_instance."""

    url_name = "deny-stub"
    menu_label = "Deny Stub"
    model = StubModel
    instance_view = _StubInstanceView


class PermissiveConfig(ListViewConfig):
    url_name = "allow-stub"
    menu_label = "Allow Stub"
    model = StubModel
    instance_view = _StubInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class ScopedConfig(ListViewConfig):
    """Declares a scope attribute the framework has never heard of.

    "tenant" is deliberately not a word panel_framework knows: the prologue
    must deny on whatever name a config declares, not on a hard-coded one.
    """

    url_name = "scoped-stub"
    menu_label = "Scoped Stub"
    model = StubModel
    instance_view = _StubInstanceView
    required_request_attrs = ("tenant",)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class ScopeDereferencingConfig(ListViewConfig):
    """authorise_instance dereferences the scope this config declares.

    Used to prove the prologue's checks run, and raise Http404, before this
    override ever executes — if it ran on a bare request this line would
    raise AttributeError instead.
    """

    url_name = "scope-deref-stub"
    menu_label = "Scope Deref Stub"
    model = StubModel
    instance_view = _StubInstanceView
    required_request_attrs = ("tenant",)

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        _ = request.tenant.pk


def _authenticated_request(path: str) -> HttpRequest:
    """A request carrying an authenticated user and no scope attribute at all.

    That is what a host app sends for a config that declares no
    required_request_attrs: get_scope's default needs nothing further, so
    the prologue is satisfied without one.
    """
    request = RequestFactory().get(path)
    request.user = make_staff_user()
    return request


@pytest.mark.django_db
class TestCheckAccessDenyByDefault:
    def test_config_without_authorise_instance_override_404s_on_detail_path(
        self, mock_site_context: None
    ) -> None:
        stub = make_stub(name="Denied Stub")
        request = _authenticated_request(f"/test-panel/deny-stub/{stub.pk}")
        with pytest.raises(Http404):
            panel_framework_view(
                config=[NavGroup("Stubs", [DenyByDefaultConfig])],
                request=request,
                path_string=f"deny-stub/{stub.pk}",
                template_name=INTERFACE_TEMPLATE,
                url_name=INTERFACE_URL_NAME,
            )

    def test_config_declaring_no_scope_serves_a_detail_path_unscoped(
        self, mock_site_context: None
    ) -> None:
        """The standalone-host case: a config that overrides authorise_instance
        but declares no required_request_attrs is served on a request that
        carries no scope of any kind."""
        stub = make_stub(name="Allowed Stub")
        request = _authenticated_request(f"/test-panel/allow-stub/{stub.pk}")
        response = panel_framework_view(
            config=[NavGroup("Stubs", [PermissiveConfig])],
            request=request,
            path_string=f"allow-stub/{stub.pk}",
            template_name=INTERFACE_TEMPLATE,
            url_name=INTERFACE_URL_NAME,
        )
        assert response.status_code == 200
        assert "Allowed Stub" in response.content.decode()


class TestCheckAccessPrologueIsNonBypassable:
    """The prologue denies on two independent grounds -- no authenticated user,
    and a declared scope attribute that is missing. Both are pinned against
    configs whose override would otherwise let the request through."""

    @pytest.mark.django_db
    def test_request_missing_a_declared_scope_attribute_is_denied(
        self, mock_site_context: None
    ) -> None:
        request = RequestFactory().get("/test-panel/scoped-stub/1")
        request.user = make_staff_user()

        with pytest.raises(Http404):
            ScopedConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_request_without_an_authenticated_user_is_denied(self) -> None:
        request = RequestFactory().get("/test-panel/scoped-stub/1")
        request.tenant = object()

        with pytest.raises(Http404):
            ScopedConfig.check_access(request, StubModel(pk=1, name="unsaved"))

    def test_bare_request_raises_http404_even_when_override_dereferences_the_scope(
        self,
    ) -> None:
        """The non-overridable prologue must deny before authorise_instance
        runs, even for a subclass whose override would blow up if it ran."""
        instance = StubModel(pk=1, name="unsaved")
        with pytest.raises(Http404):
            ScopeDereferencingConfig.check_access(HttpRequest(), instance)


@pytest.mark.django_db
class TestOutOfScopeActionRequests:
    """An action the page offered can 404 once its object leaves the user's
    scope. htmx drops a bare 404, so the user would see nothing happen."""

    def _dispatch(
        self, path_string: str, **headers: str
    ) -> HttpResponse | StreamingHttpResponse:
        request = RequestFactory().delete(f"/test-panel/{path_string}", **headers)
        request.user = make_staff_user()
        return panel_framework_view(
            config=[NavGroup("Stubs", [DenyByDefaultConfig])],
            request=request,
            path_string=path_string,
            template_name=INTERFACE_TEMPLATE,
            url_name=INTERFACE_URL_NAME,
        )

    def test_htmx_action_request_gets_the_unavailable_fragment_with_404(
        self, mock_site_context: None
    ) -> None:
        stub = make_stub(name="Gone Stub")

        response = self._dispatch(
            f"deny-stub/{stub.pk}/__actions/delete", HTTP_HX_REQUEST="true"
        )

        assert isinstance(response, HttpResponse)
        assert response.status_code == 404
        html = response.content.decode()
        assert "data-htmx-swap-error" in html
        assert "This is no longer available" in html
        assert "Gone Stub" not in html

    def test_plain_action_request_still_raises_http404(
        self, mock_site_context: None
    ) -> None:
        stub = make_stub(name="Gone Stub")

        with pytest.raises(Http404):
            self._dispatch(f"deny-stub/{stub.pk}/__actions/delete")

    def test_htmx_request_for_a_page_still_raises_http404(
        self, mock_site_context: None
    ) -> None:
        stub = make_stub(name="Gone Stub")

        with pytest.raises(Http404):
            self._dispatch(f"deny-stub/{stub.pk}", HTTP_HX_REQUEST="true")


# Tests for _build_breadcrumbs.


class _CrumbCohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = StubModel


class _CrumbUsersConfig(ListViewConfig):
    url_name = "users"
    menu_label = "Users"
    model = StubModel


class _CrumbOrganisationConfig(ObjectViewConfig):
    url_name = "organisation"
    menu_label = "Organisation"
    instance_view = InstanceView

    @classmethod
    def get_object(cls, request: HttpRequest) -> StubModel:
        raise NotImplementedError


class _CrumbDashboardConfig(BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    panel = StubDataTablePanel


CRUMB_SECTIONS = {
    "cohorts": _CrumbCohortsConfig,
    "users": _CrumbUsersConfig,
    "organisation": _CrumbOrganisationConfig,
    "dashboard": _CrumbDashboardConfig,
}


class TestBuildBreadcrumbs:
    def test_root_no_parts(self) -> None:
        assert _build_breadcrumbs([], CRUMB_SECTIONS, INTERFACE_URL_NAME) == []

    def test_section_list_page(self) -> None:
        crumbs = _build_breadcrumbs(["cohorts"], CRUMB_SECTIONS, INTERFACE_URL_NAME)

        assert crumbs == [{"label": "Cohorts"}]

    @pytest.mark.django_db
    def test_instance_page(self, mock_site_context: None) -> None:
        instance = make_stub(name="Test Cohort")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            CRUMB_SECTIONS,
            INTERFACE_URL_NAME,
            current_instance=instance,
        )

        assert crumbs == [
            {"label": "Cohorts", "url": "/test-panel/cohorts"},
            {"label": "Test Cohort"},
        ]

    def test_unknown_section_returns_empty(self) -> None:
        assert (
            _build_breadcrumbs(["nonexistent"], CRUMB_SECTIONS, INTERFACE_URL_NAME)
            == []
        )

    @pytest.mark.django_db
    def test_extra_url_kwargs_merge_into_section_crumb_url(
        self, mock_site_context: None
    ) -> None:
        instance = make_stub(name="Test Cohort")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            CRUMB_SECTIONS,
            "panel_framework_test:scoped_interface",
            current_instance=instance,
            extra_url_kwargs={"extra": "acme"},
        )

        assert crumbs[0] == {
            "label": "Cohorts",
            "url": "/test-panel/scoped/acme/cohorts",
        }

    @pytest.mark.django_db
    def test_tab_page_shows_instance_as_current(self, mock_site_context: None) -> None:
        instance = make_stub(name="Tab Test")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk), "__tabs", "details"],
            CRUMB_SECTIONS,
            INTERFACE_URL_NAME,
            current_instance=instance,
        )

        assert crumbs == [
            {"label": "Cohorts", "url": "/test-panel/cohorts"},
            {"label": "Tab Test"},
        ]

    @pytest.mark.django_db
    def test_object_view_is_its_section_alone(self, mock_site_context: None) -> None:
        instance = make_stub(name="Acme")

        crumbs = _build_breadcrumbs(
            ["organisation"],
            CRUMB_SECTIONS,
            INTERFACE_URL_NAME,
            current_instance=instance,
        )

        assert crumbs == [{"label": "Organisation"}]

    def test_base_view_is_its_section_alone(self) -> None:
        crumbs = _build_breadcrumbs(["dashboard"], CRUMB_SECTIONS, INTERFACE_URL_NAME)

        assert crumbs == [{"label": "Dashboard"}]
