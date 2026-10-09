"""Row selection and bulk actions: payload resolution, and the
confirm-then-act flow a bulk-action POST runs through, with JavaScript on or
off."""

from __future__ import annotations

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.panel_framework.bulk_actions import Selection, resolve_selection
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.views import (
    SectionConfigBase,
    _handle_action,
    _ResolvedAction,
)

from .helpers import make_staff_user, make_stub
from .stub_models import StubModel
from .stub_panels import StubBulkAction, StubDataTablePanel
from .view_helpers import call_view, fetch

pytestmark = pytest.mark.django_db


def _panel_path(stub_pk: object) -> str:
    return f"stubs/{stub_pk}/__tabs/default"


def _action_path(stub_pk: object, action_name: str = "stub_bulk") -> str:
    return f"{_panel_path(stub_pk)}/__actions/{action_name}"


# -- resolve_selection ----------------------------------------------------


class _NarrowedTablePanel(StubDataTablePanel):
    """The same table, scoped to rows whose name starts with "keep"."""

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(name__startswith="keep")


def test_keys_outside_scope_are_dropped(mock_site_context: Site) -> None:
    kept = make_stub(name="keep-me")
    outside = make_stub(name="drop-me")
    request = RequestFactory().post("/stubs")
    panel = _NarrowedTablePanel(
        PanelContext(
            request=request,
            instance=None,
            base_url="/stubs",
            name="",
            config=SectionConfigBase,
        )
    )

    queryset = resolve_selection(
        panel, request, Selection(mode="keys", keys=[str(kept.pk), str(outside.pk)])
    )

    assert list(queryset) == [kept]


def test_malformed_keys_are_dropped(mock_site_context: Site) -> None:
    kept = make_stub(name="keep-me")
    request = RequestFactory().post("/stubs")
    panel = StubDataTablePanel(
        PanelContext(
            request=request,
            instance=None,
            base_url="/stubs",
            name="",
            config=SectionConfigBase,
        )
    )

    queryset = resolve_selection(
        panel, request, Selection(mode="keys", keys=[str(kept.pk), "not-an-int"])
    )

    assert list(queryset) == [kept]


# -- the confirm-then-act flow, through the resolved URL -------------------


def test_unpermitted_action_is_403(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk, "stub_forbidden_bulk"),
        method="post",
        data={"mode": "keys", "keys": [str(stub.pk)]},
    )

    assert response.status_code == 403


def test_zero_rows_is_rejected_with_422(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(_action_path(stub.pk), method="post", data={"mode": "keys"})

    assert response.status_code == 422
    assert "Nothing selected" in response.content.decode()


def test_all_matching_mode_is_422(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk), method="post", data={"mode": "all_matching"}
    )

    assert response.status_code == 422
    assert "Not supported yet" in response.content.decode()


def test_over_max_rows_is_rejected_with_422(mock_site_context: Site) -> None:
    """max_rows is read from the action, not hard-coded — set to 2 here so
    3 resolved rows is already over the cap."""

    class _LowLimitBulkAction(StubBulkAction):
        max_rows = 2

    stubs = [make_stub(name=f"row-{i}") for i in range(3)]
    request = RequestFactory().post(
        "/stubs/__actions/stub_bulk",
        {"mode": "keys", "keys": [str(stub.pk) for stub in stubs]},
        HTTP_HX_REQUEST="true",
    )
    request.user = make_staff_user()
    panel = StubDataTablePanel(
        PanelContext(
            request=request,
            instance=None,
            base_url="/stubs",
            name="",
            config=SectionConfigBase,
            page_url="/stubs",
        )
    )
    resolved = _ResolvedAction(_LowLimitBulkAction(), panel.ctx)

    response = _handle_action(request, resolved, panel)

    assert isinstance(response, HttpResponse)
    assert response.status_code == 422
    assert "3 selected; the limit is 2" in response.content.decode()


def test_confirmation_count_matches_execution(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]
    keys = [str(stub.pk) for stub in stubs]

    confirm_response = fetch(
        _action_path(stubs[0].pk), method="post", data={"mode": "keys", "keys": keys}
    )
    assert confirm_response.status_code == 200
    assert "This will affect 3 stub models." in confirm_response.content.decode()

    execute_response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "keys", "keys": keys, "confirmed": "1"},
    )

    assert execute_response.status_code == 303
    assert not StubModel.objects.filter(is_active=True).exists()


def test_redirect_keeps_table_state(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")
    path = _action_path(stub.pk)
    expected_location = f"/test-panel/framework/{_panel_path(stub.pk)}?stub-sort=name"
    data = {"mode": "keys", "keys": [str(stub.pk)], "confirmed": "1"}

    plain_request = RequestFactory().post(
        f"/test-panel/framework/{path}?stub-sort=name", data
    )
    plain_request.user = make_staff_user()
    plain_response = call_view(plain_request, path)
    assert plain_response.status_code == 303
    assert plain_response["Location"] == expected_location

    htmx_request = RequestFactory().post(
        f"/test-panel/framework/{path}?stub-sort=name", data, HTTP_HX_REQUEST="true"
    )
    htmx_request.user = make_staff_user()
    htmx_response = call_view(htmx_request, path)
    assert htmx_response.status_code == 204
    assert htmx_response["HX-Redirect"] == expected_location


@pytest.mark.parametrize("htmx", [True, False])
def test_confirm_form_carries_table_state(mock_site_context: Site, htmx: bool) -> None:
    """The confirm POST must carry the table's query on to the redirect, so
    confirming doesn't reset the page, sort and filters."""
    stub = make_stub(name="row-x")
    path = _action_path(stub.pk)
    query = "?stub-page=1&stub-sort=-name"
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = RequestFactory().post(
        f"/test-panel/framework/{path}{query}",
        {"mode": "keys", "keys": [str(stub.pk)]},
        **headers,
    )
    request.user = make_staff_user()

    response = call_view(request, path)

    document = lxml.html.fromstring(response.content.decode())
    (form,) = [
        form
        for form in document.cssselect("form")
        if form.cssselect("input[name='confirmed']")
    ]
    expected_action = f"/test-panel/framework/{path}{query}"
    assert form.get("action") == expected_action
    assert form.get("hx-post") == expected_action
    if not htmx:
        (cancel,) = [a for a in document.cssselect("a") if a.text_content() == "Cancel"]
        expected_cancel = f"/test-panel/framework/{_panel_path(stub.pk)}{query}"
        assert cancel.get("href") == expected_cancel


def test_plain_post_renders_full_page_confirmation(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk),
        method="post",
        data={"mode": "keys", "keys": [str(stub.pk)]},
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "This will affect 1 stub models." in content
    assert "<html" in content.lower()


def test_plain_post_error_is_full_page_422(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk), method="post", data={"mode": "all_matching"}
    )

    content = response.content.decode()
    assert response.status_code == 422
    assert "Not supported yet" in content
    assert "<html" in content.lower()


def test_htmx_post_renders_modal_confirmation(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk),
        method="post",
        data={"mode": "keys", "keys": [str(stub.pk)]},
        htmx=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in content.lower()
    assert "This will affect 1 stub models." in content


# -- rendering ---------------------------------------------------------


def test_only_permitted_bulk_actions_render_in_the_bar(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(_panel_path(stub.pk)).content.decode()

    assert 'name="keys"' in html
    assert "Mark processed" in html
    assert "Forbidden bulk action" not in html


def test_selection_ui_hidden_without_permitted_actions(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    html = fetch(f"stubs/{stub.pk}/__tabs/pair").content.decode()

    document = lxml.html.fromstring(html)
    (table_b,) = document.cssselect("#b-table")
    assert table_b.cssselect('input[name="keys"]') == []
    assert table_b.cssselect('[aria-live="polite"]') == []
