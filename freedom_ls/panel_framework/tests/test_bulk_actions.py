"""Row selection and bulk actions: payload resolution, and the
confirm-then-act flow a bulk-action POST runs through, with JavaScript on or
off."""

from __future__ import annotations

import json

import lxml.html
import pytest

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.db.models import Model, QuerySet
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from freedom_ls.panel_framework.bulk_actions import (
    FAILED_REASON,
    BackgroundRun,
    BulkAction,
    BulkCount,
    BulkOutcome,
    BulkResult,
    BulkResultEntry,
    Selection,
    resolve_selection,
)
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


def test_confirmed_htmx_post_returns_result_summary(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]
    keys = [str(stub.pk) for stub in stubs]

    confirm_response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "keys", "keys": keys},
        htmx=True,
    )
    assert "This will affect 3 stub models." in confirm_response.content.decode()

    execute_response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "keys", "keys": keys, "confirmed": "1", "expected_count": "3"},
        htmx=True,
    )

    content = execute_response.content.decode()
    assert execute_response.status_code == 200
    assert "<html" not in content.lower()
    assert "3 stub models changed." in content
    assert not StubModel.objects.filter(is_active=True).exists()
    trigger = json.loads(execute_response["HX-Trigger"])
    assert sorted(trigger["itemChanged"]["ids"]) == sorted(keys)


def test_confirmed_plain_post_returns_result_page_with_back_link(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-x")
    path = _action_path(stub.pk)
    request = RequestFactory().post(
        f"/test-panel/framework/{path}?stub-sort=name",
        {
            "mode": "keys",
            "keys": [str(stub.pk)],
            "confirmed": "1",
            "expected_count": "1",
        },
    )
    request.user = make_staff_user()

    response = call_view(request, path)

    content = response.content.decode()
    assert response.status_code == 200
    assert "<html" in content.lower()
    assert "1 stub model changed." in content
    document = lxml.html.fromstring(content)
    (back,) = [
        a for a in document.cssselect("a") if a.text_content().startswith("Back to")
    ]
    expected = f"/test-panel/framework/{_panel_path(stub.pk)}?stub-sort=name"
    assert back.get("href") == expected


def test_result_lists_skipped_objects_with_reasons(mock_site_context: Site) -> None:
    class _SkippingBulkAction(StubBulkAction):
        def apply(
            self,
            user: AbstractBaseUser | AnonymousUser,
            obj: Model,
            cleaned_data: dict[str, object],
        ) -> BulkOutcome:
            return BulkOutcome("skipped", "already processed")

    stubs = [make_stub(name=f"row-{i}") for i in range(2)]
    request = RequestFactory().post(
        "/stubs/__actions/stub_bulk",
        {
            "mode": "keys",
            "keys": [str(stub.pk) for stub in stubs],
            "confirmed": "1",
            "expected_count": "2",
        },
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

    response = _handle_action(
        request, _ResolvedAction(_SkippingBulkAction(), panel.ctx), panel
    )

    assert isinstance(response, HttpResponse)
    content = response.content.decode()
    assert "0 stub models changed." in content
    assert "2 already processed" in content
    assert "row-0: already processed" in content


class _PartlyFailingBulkAction(StubBulkAction):
    """Raises on the row named "boom"."""

    def apply(
        self,
        user: AbstractBaseUser | AnonymousUser,
        obj: Model,
        cleaned_data: dict[str, object],
    ) -> BulkOutcome:
        outcome = super().apply(user, obj, cleaned_data)
        if obj.name == "boom":
            raise ValueError("secret detail")
        return outcome


def _run_partly_failing(action: BulkAction, stubs: list[StubModel]) -> BulkResult:
    request = RequestFactory().post("/stubs")
    request.user = make_staff_user()
    queryset = StubModel.objects.filter(pk__in=[stub.pk for stub in stubs]).order_by(
        "pk"
    )
    result = action.execute(request, queryset, {})
    assert isinstance(result, BulkResult)
    return result


def test_declared_failure_exception_becomes_failed_entry(
    mock_site_context: Site,
) -> None:
    class _Action(_PartlyFailingBulkAction):
        failure_exceptions = (ValueError,)

    stubs = [make_stub(name="ok"), make_stub(name="boom")]

    result = _run_partly_failing(_Action(), stubs)

    assert result.changed == 1
    assert [(e.row_label, e.status, e.reason) for e in result.entries] == [
        ("boom", "failed", FAILED_REASON)
    ]
    assert "secret detail" not in str(result.to_json())


def test_undeclared_exception_propagates(mock_site_context: Site) -> None:
    stubs = [make_stub(name="boom")]

    with pytest.raises(ValueError, match="secret detail"):
        _run_partly_failing(_PartlyFailingBulkAction(), stubs)


@pytest.mark.django_db(transaction=True)
def test_each_apply_runs_in_its_own_transaction(mock_site_context: Site) -> None:
    class _Action(_PartlyFailingBulkAction):
        failure_exceptions = (ValueError,)

    stubs = [make_stub(name="a"), make_stub(name="b"), make_stub(name="boom")]

    _run_partly_failing(_Action(), stubs)

    inactive = set(
        StubModel.objects.filter(is_active=False).values_list("name", flat=True)
    )
    assert inactive == {"a", "b"}


def test_bulk_result_round_trips_through_json() -> None:
    result = BulkResult(
        counts=[BulkCount("changed", "", 2), BulkCount("skipped", "already", 1)],
        entries=[BulkResultEntry("7", "row", "skipped", "already")],
        left_out=3,
    )

    assert BulkResult.from_json(json.loads(json.dumps(result.to_json()))) == result


def test_confirmed_post_redirects_to_result_url_for_background_run(
    mock_site_context: Site,
) -> None:
    class _BackgroundAction(StubBulkAction):
        def execute(
            self,
            request: HttpRequest,
            queryset: QuerySet,
            cleaned_data: dict[str, object],
        ) -> BackgroundRun:
            return BackgroundRun("/runs/1")

    stub = make_stub(name="row-x")
    data = {
        "mode": "keys",
        "keys": [str(stub.pk)],
        "confirmed": "1",
        "expected_count": "1",
    }
    responses = []
    for headers in ({}, {"HTTP_HX_REQUEST": "true"}):
        request = RequestFactory().post("/stubs/__actions/stub_bulk", data, **headers)
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
        responses.append(
            _handle_action(
                request, _ResolvedAction(_BackgroundAction(), panel.ctx), panel
            )
        )

    plain, htmx = responses
    assert isinstance(plain, HttpResponse)
    assert isinstance(htmx, HttpResponse)
    assert (plain.status_code, plain["Location"]) == (303, "/runs/1")
    assert (htmx.status_code, htmx["HX-Redirect"]) == (204, "/runs/1")


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


# -- classification, skip counts and the guarded confirm --------------------


def _classified_post(
    stubs: list[StubModel], **extra: object
) -> tuple[str, dict[str, object]]:
    path = _action_path(stubs[0].pk, "stub_classifying_bulk")
    data: dict[str, object] = {
        "mode": "keys",
        "keys": [str(stub.pk) for stub in stubs],
        **extra,
    }
    return path, data


def test_confirmation_shows_changed_and_skipped_counts(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}", is_active=i >= 2) for i in range(5)]
    path, data = _classified_post(stubs)

    response = fetch(path, method="post", data=data, htmx=True)

    content = response.content.decode()
    assert response.status_code == 200
    assert "This will affect 3 stub models." in content
    assert "2 are already processed and will be skipped." in content


def test_confirmation_uses_singular_verb_for_one_skip(mock_site_context: Site) -> None:
    stubs = [make_stub(name="row-a", is_active=False), make_stub(name="row-b")]
    path, data = _classified_post(stubs)

    response = fetch(path, method="post", data=data, htmx=True)

    assert "1 is already processed and will be skipped." in response.content.decode()


def test_confirm_is_disabled_when_nothing_would_change(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}", is_active=False) for i in range(2)]
    path, data = _classified_post(stubs)

    response = fetch(path, method="post", data=data, htmx=True)

    document = lxml.html.fromstring(response.content.decode())
    (submit,) = document.cssselect("form button[type='submit']")
    assert submit.get("disabled") is not None
    assert "2 are already processed and will be skipped." in response.content.decode()


def test_confirm_is_enabled_when_something_would_change(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name="row-a"), make_stub(name="row-b", is_active=False)]
    path, data = _classified_post(stubs)

    response = fetch(path, method="post", data=data, htmx=True)

    document = lxml.html.fromstring(response.content.decode())
    (submit,) = document.cssselect("form button[type='submit']")
    assert submit.get("disabled") is None


def test_confirmation_carries_expected_count_to_the_confirm_form(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]

    response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "keys", "keys": [str(stub.pk) for stub in stubs]},
        htmx=True,
    )

    document = lxml.html.fromstring(response.content.decode())
    (field,) = document.cssselect("input[name='expected_count']")
    assert field.get("value") == "3"


def test_confirmed_post_without_expected_count_is_422(mock_site_context: Site) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk),
        method="post",
        data={"mode": "keys", "keys": [str(stub.pk)], "confirmed": "1"},
        htmx=True,
    )

    assert response.status_code == 422
    assert StubModel.objects.filter(is_active=True).exists()


def test_confirmed_post_with_non_integer_expected_count_is_422(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="row-x")

    response = fetch(
        _action_path(stub.pk),
        method="post",
        data={
            "mode": "keys",
            "keys": [str(stub.pk)],
            "confirmed": "1",
            "expected_count": "many",
        },
        htmx=True,
    )

    assert response.status_code == 422
    assert StubModel.objects.filter(is_active=True).exists()


def test_expected_count_mismatch_is_422_and_changes_nothing(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]
    path, data = _classified_post(stubs, confirmed="1", expected_count="2")

    response = fetch(path, method="post", data=data, htmx=True)

    content = response.content.decode()
    assert response.status_code == 422
    assert "The selection changed since you opened this." in content
    assert "This will affect 3 stub models." in content
    document = lxml.html.fromstring(content)
    (field,) = document.cssselect("input[name='expected_count']")
    assert field.get("value") == "3"
    assert StubModel.objects.filter(is_active=True).count() == 3


def test_confirmed_post_with_matching_expected_count_runs(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]
    path, data = _classified_post(stubs, confirmed="1", expected_count="3")

    response = fetch(path, method="post", data=data, htmx=True)

    assert response.status_code == 200
    assert "3 stub models changed." in response.content.decode()
    assert not StubModel.objects.filter(is_active=True).exists()


def test_confirmed_post_that_would_change_nothing_is_422(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}", is_active=False) for i in range(2)]
    path, data = _classified_post(stubs, confirmed="1", expected_count="2")

    response = fetch(path, method="post", data=data, htmx=True)

    assert response.status_code == 422
    assert "changed" not in response.content.decode().split("skipped.")[-1]


def test_plain_post_confirmation_shows_skip_counts(mock_site_context: Site) -> None:
    stubs = [make_stub(name="row-a"), make_stub(name="row-b", is_active=False)]
    path, data = _classified_post(stubs)

    response = fetch(path, method="post", data=data)

    content = response.content.decode()
    assert "<html" in content.lower()
    assert "1 is already processed and will be skipped." in content


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
