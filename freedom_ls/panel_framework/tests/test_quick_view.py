"""Tests for the __quick-view route: panel_framework/quick_view.py and its
dispatch in panel_framework/views.py."""

from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.panel_framework.quick_view import QuickView
from freedom_ls.panel_framework.views import InstanceView, ListViewConfig, NavGroup

from .helpers import make_stub
from .stub_models import StubModel
from .stub_panels import StubDataTable, StubDetailsPanel, StubQuickView
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db


class _StubQuickViewInstanceView(InstanceView):
    panel = StubDetailsPanel


class _QuickViewStubConfig(ListViewConfig):
    """Permissive: every stub's quick view is served."""

    url_name = "quick-view-stub"
    menu_label = "Quick View Stub"
    model = StubModel
    instance_view = _StubQuickViewInstanceView
    quick_view = StubQuickView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class _NoQuickViewStubConfig(ListViewConfig):
    """Permissive, but declares no quick view at all."""

    url_name = "no-quick-view-stub"
    menu_label = "No Quick View Stub"
    model = StubModel
    instance_view = _StubQuickViewInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


class _DeniedQuickViewStubConfig(ListViewConfig):
    """Denies any stub named "secret", the _FirstStubConfig pattern from
    test_configs.py applied to a ListViewConfig instead of an ObjectViewConfig."""

    url_name = "denied-quick-view-stub"
    menu_label = "Denied Quick View Stub"
    model = StubModel
    instance_view = _StubQuickViewInstanceView
    quick_view = StubQuickView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        if instance.name.startswith("secret"):
            raise Http404


class _PagelessQuickViewStubConfig(ListViewConfig):
    """Rows with no page of their own, opened only in the drawer. Denies any
    stub named "secret"."""

    url_name = "pageless-quick-view-stub"
    menu_label = "Pageless Quick View Stub"
    model = StubModel
    list_view = StubDataTable
    table_key = "pageless"
    quick_view = StubQuickView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        if instance.name.startswith("secret"):
            raise Http404


CONFIG = [
    NavGroup(
        "Quick view stubs",
        [
            _QuickViewStubConfig,
            _NoQuickViewStubConfig,
            _DeniedQuickViewStubConfig,
            _PagelessQuickViewStubConfig,
        ],
    )
]


def _view(path_string: str, **request_kwargs: object) -> HttpResponse:
    response = call_view(
        make_request(path_string, **request_kwargs), path_string, CONFIG
    )
    assert isinstance(response, HttpResponse)
    return response


def test_an_htmx_get_of_quick_view_returns_the_frame_with_the_consumers_fields(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Ada")

    response = _view(f"quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    html = response.content.decode()
    assert response.status_code == 200
    assert f'data-quick-view-title="{stub}"' in html
    assert f'data-entity-id="{stub.pk}"' in html
    assert 'data-refresh-events="itemChanged"' in html
    assert "Ada" in html


def assert_unavailable_dialog(response: HttpResponse) -> None:
    assert response.status_code == 404
    assert "This is no longer available" in response.content.decode()


def test_quick_view_route_404s_when_the_config_declares_no_quick_view(
    mock_site_context: Site,
) -> None:
    stub = make_stub()

    response = _view(f"no-quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert_unavailable_dialog(response)


def test_quick_view_route_404s_when_authorise_instance_denies_the_stub(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="secret-stub")

    response = _view(f"denied-quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert_unavailable_dialog(response)
    assert "secret-stub" not in response.content.decode()


def test_a_non_htmx_get_of_quick_view_redirects_to_the_instance_page(
    mock_site_context: Site,
) -> None:
    stub = make_stub()

    response = _view(f"quick-view-stub/{stub.pk}/__quick-view")

    assert response.status_code == 302
    assert response["Location"] == f"/test-panel/framework/quick-view-stub/{stub.pk}"


def test_quick_view_after_a_tabs_segment_404s(mock_site_context: Site) -> None:
    stub = make_stub()

    response = fetch(f"stubs/{stub.pk}/__tabs/details/__quick-view", htmx=True)

    assert_unavailable_dialog(response)


def test_quick_view_response_varies_on_hx_request(mock_site_context: Site) -> None:
    stub = make_stub()

    response = _view(f"quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert "HX-Request" in response["Vary"]


def test_the_frame_carries_the_consumers_subtitle(mock_site_context: Site) -> None:
    stub = make_stub(name="Ada")

    response = _view(f"quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert 'data-quick-view-subtitle=""' in response.content.decode()


def test_a_quick_view_has_no_subtitle_unless_its_consumer_gives_one() -> None:
    assert (
        QuickView(RequestFactory().get("/"), StubModel(name="Ada")).get_subtitle() == ""
    )


def test_a_row_with_no_page_of_its_own_opens_in_the_quick_view(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Ada")

    response = _view(f"pageless-quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert response.status_code == 200
    assert f'data-entity-id="{stub.pk}"' in response.content.decode()


def test_a_pageless_quick_view_of_a_malformed_pk_is_unavailable(
    mock_site_context: Site,
) -> None:
    response = _view("pageless-quick-view-stub/not-a-number/__quick-view", htmx=True)

    assert_unavailable_dialog(response)


def test_a_pageless_quick_view_still_runs_authorise_instance(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="secret-stub")

    response = _view(f"pageless-quick-view-stub/{stub.pk}/__quick-view", htmx=True)

    assert_unavailable_dialog(response)
    assert "secret-stub" not in response.content.decode()


def test_a_non_htmx_get_of_a_pageless_quick_view_redirects_to_the_list(
    mock_site_context: Site,
) -> None:
    stub = make_stub()

    response = _view(f"pageless-quick-view-stub/{stub.pk}/__quick-view")

    assert response.status_code == 302
    assert response["Location"] == "/test-panel/framework/pageless-quick-view-stub"


def test_a_pageless_row_still_has_no_page(mock_site_context: Site) -> None:
    stub = make_stub()

    with pytest.raises(Http404):
        _view(f"pageless-quick-view-stub/{stub.pk}")
