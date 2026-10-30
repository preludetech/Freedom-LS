"""Row selection and bulk actions: payload resolution, and the
confirm-then-act flow a bulk-action POST runs through, with JavaScript on or
off."""

from __future__ import annotations

import json
import uuid
from typing import cast

import lxml.html
import pytest

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sites.models import Site
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
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
from freedom_ls.panel_framework.bulk_runs import run_bulk_action
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.models import BulkActionRun, RunStatus
from freedom_ls.panel_framework.views import (
    REFRESH_IDS_LIMIT,
    SectionConfigBase,
    _handle_action,
    _ResolvedAction,
)

from .helpers import make_staff_user, make_stub
from .stub_models import StubModel
from .stub_panels import (
    RecordingCapabilityConfig,
    StubBulkAction,
    StubDataTablePanel,
    StubRecordedBulkAction,
)
from .view_helpers import call_view, fetch, make_request

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


def _stub_panel(request: HttpRequest) -> StubDataTablePanel:
    return StubDataTablePanel(
        PanelContext(
            request=request,
            instance=None,
            base_url="/stubs",
            name="",
            config=SectionConfigBase,
        )
    )


def test_all_matching_resolves_through_the_tables_search(
    mock_site_context: Site,
) -> None:
    hit = make_stub(name="needle-1")
    make_stub(name="hay-1")
    request = RequestFactory().post("/stubs?stub-q=needle")

    queryset = resolve_selection(
        _stub_panel(request), request, Selection(mode="all_matching")
    )

    assert list(queryset) == [hit]


def test_all_matching_resolves_through_the_tables_filters(
    mock_site_context: Site,
) -> None:
    active = make_stub(name="a", is_active=True)
    make_stub(name="b", is_active=False)
    request = RequestFactory().post("/stubs?stub-active=1")

    queryset = resolve_selection(
        _stub_panel(request), request, Selection(mode="all_matching")
    )

    assert list(queryset) == [active]


def test_all_matching_honours_excluded_keys(mock_site_context: Site) -> None:
    kept = make_stub(name="a")
    dropped = make_stub(name="b")
    request = RequestFactory().post("/stubs")

    queryset = resolve_selection(
        _stub_panel(request),
        request,
        Selection(mode="all_matching", excluded=[str(dropped.pk), "not-an-int"]),
    )

    assert list(queryset) == [kept]


def test_all_matching_never_leaves_the_panels_scope(mock_site_context: Site) -> None:
    kept = make_stub(name="keep-me")
    make_stub(name="drop-me")
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

    queryset = resolve_selection(panel, request, Selection(mode="all_matching"))

    assert list(queryset) == [kept]


def _post_all_matching(action: BulkAction) -> HttpResponse:
    request = RequestFactory().post(
        "/stubs/__actions/stub_bulk", {"mode": "all_matching"}, HTTP_HX_REQUEST="true"
    )
    request.user = make_staff_user()
    panel = _stub_panel(request)
    response = _handle_action(request, _ResolvedAction(action, panel.ctx), panel)
    assert isinstance(response, HttpResponse)
    return response


def test_all_matching_over_max_rows_is_422_when_it_would_run_inline(
    mock_site_context: Site,
) -> None:
    class _LowLimitBulkAction(StubBulkAction):
        max_rows = 2

    for i in range(3):
        make_stub(name=f"row-{i}")

    response = _post_all_matching(_LowLimitBulkAction())

    assert response.status_code == 422
    assert "3 matching; the limit is 2" in response.content.decode()


def test_all_matching_over_max_rows_is_allowed_when_it_runs_in_background(
    mock_site_context: Site,
) -> None:
    class _LowLimitBackgroundAction(StubBulkAction):
        max_rows = 2

        def runs_in_background(self, count: int) -> bool:
            return True

    stubs = [make_stub(name=f"row-{i}") for i in range(3)]

    response = _post_all_matching(_LowLimitBackgroundAction())

    assert response.status_code == 200
    assert f"This will affect {len(stubs)} stub models." in response.content.decode()


def test_all_matching_confirm_form_carries_mode_and_excluded(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]

    response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "all_matching", "excluded": [str(stubs[2].pk)]},
        htmx=True,
    )

    document = lxml.html.fromstring(response.content.decode())
    (mode,) = document.cssselect("input[name='mode']")
    assert mode.get("value") == "all_matching"
    excluded = [i.get("value") for i in document.cssselect("input[name='excluded']")]
    assert excluded == [str(stubs[2].pk)]
    assert not document.cssselect("input[name='keys']")
    assert "This will affect 2 stub models." in response.content.decode()


def test_all_matching_confirmed_post_changes_only_unexcluded_rows(
    mock_site_context: Site,
) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]

    response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={
            "mode": "all_matching",
            "excluded": [str(stubs[2].pk)],
            "confirmed": "1",
            "expected_count": "2",
        },
        htmx=True,
    )

    assert response.status_code == 200
    assert list(StubModel.objects.filter(is_active=True)) == [stubs[2]]


def test_all_matching_expected_count_mismatch_is_422(mock_site_context: Site) -> None:
    stubs = [make_stub(name=f"row-{i}") for i in range(3)]

    response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={"mode": "all_matching", "confirmed": "1", "expected_count": "2"},
        htmx=True,
    )

    assert response.status_code == 422
    assert StubModel.objects.filter(is_active=True).count() == 3


def test_selection_bar_renders_counts_and_a_live_region(
    mock_site_context: Site,
) -> None:
    for i in range(3):
        make_stub(name=f"row-{i}")

    html = fetch(_panel_path(StubModel.objects.first().pk)).content.decode()

    document = lxml.html.fromstring(html)
    (bar,) = document.cssselect("[data-total-count]")
    assert bar.get("data-total-count") == "3"
    assert bar.get("data-page-count") == "3"
    assert document.cssselect("[role='status']")
    assert document.cssselect("input[name='mode'][x-ref='modeInput']")
    assert document.cssselect("[x-ref='excluded']")


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


def test_a_result_over_many_rows_fires_its_events_without_ids(
    mock_site_context: Site,
) -> None:
    """The header carried every selected key: 250 UUIDs per refresh event,
    enough to overflow a proxy's header buffer after the changes were made."""
    stubs = [make_stub() for _ in range(REFRESH_IDS_LIMIT + 1)]
    keys = [str(stub.pk) for stub in stubs]

    execute_response = fetch(
        _action_path(stubs[0].pk),
        method="post",
        data={
            "mode": "keys",
            "keys": keys,
            "confirmed": "1",
            "expected_count": str(len(keys)),
        },
        htmx=True,
    )

    assert execute_response.status_code == 200
    assert not StubModel.objects.filter(is_active=True).exists()
    assert json.loads(execute_response["HX-Trigger"]) == {"itemChanged": {"ids": []}}


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
    ctx = PanelContext(
        request=request,
        instance=None,
        base_url="/stubs",
        name="",
        config=SectionConfigBase,
        page_url="/stubs",
    )
    queryset = StubModel.objects.filter(pk__in=[stub.pk for stub in stubs]).order_by(
        "pk"
    )
    result = action.execute(ctx, queryset, {})
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


def _post_background_confirm(
    htmx: bool,
) -> tuple[HttpResponse, StubDataTablePanel, HttpRequest]:
    class _BackgroundAction(StubBulkAction):
        def execute(
            self,
            ctx: PanelContext,
            queryset: QuerySet,
            cleaned_data: dict[str, object],
        ) -> BackgroundRun:
            return BackgroundRun("/runs/1/status")

    stub = make_stub(name="row-x")
    data = {
        "mode": "keys",
        "keys": [str(stub.pk)],
        "confirmed": "1",
        "expected_count": "1",
    }
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    request = RequestFactory().post(
        "/stubs/__actions/stub_bulk?stub-page=2", data, **headers
    )
    request.user = make_staff_user()
    request.session = {}
    request._messages = FallbackStorage(request)
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
        request, _ResolvedAction(_BackgroundAction(), panel.ctx), panel
    )
    assert isinstance(response, HttpResponse)
    return response, panel, request


def test_background_run_over_htmx_closes_the_modal_and_starts_polling(
    mock_site_context: Site,
) -> None:
    response, panel, _request = _post_background_confirm(htmx=True)

    assert response.status_code == 204
    assert "HX-Redirect" not in response
    assert json.loads(response["HX-Trigger"]) == {
        "closeModal": {},
        "bulkRunStarted": {
            "region": panel.region_id,
            "action": StubBulkAction.action_name,
            "label": StubBulkAction.label,
            "status_url": "/runs/1/status",
        },
    }


def test_background_run_without_javascript_returns_to_the_table_with_a_flash(
    mock_site_context: Site,
) -> None:
    response, _panel, request = _post_background_confirm(htmx=False)

    assert (response.status_code, response["Location"]) == (
        303,
        "/stubs?stub-page=2",
    )
    assert [str(message) for message in get_messages(request)] == [
        f"{StubBulkAction.label} is running in the background. "
        "You'll get a notification when it finishes."
    ]


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

    response = fetch(_action_path(stub.pk), method="post", data={"mode": "keys"})

    content = response.content.decode()
    assert response.status_code == 422
    assert "Nothing selected" in content
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


# -- recorded runs and their status route ---------------------------------

RECORDED_PATH = f"{StubRecordedBulkAction.__module__}.StubRecordedBulkAction"


def _recorded_run(
    requester: object, *stubs: StubModel, **fields: object
) -> BulkActionRun:
    fields.setdefault("action_path", RECORDED_PATH)
    fields.setdefault("table_key", "stubs")
    fields.setdefault("action_name", "stub_recorded")
    return cast(
        BulkActionRun,
        BulkActionRun.objects.create(
            requested_by=requester,
            keys=[str(stub.pk) for stub in stubs],
            **fields,
        ),
    )


def _poll(run: BulkActionRun, user: object | None = None):
    path = f"stubs/__runs/{run.pk}"
    request = make_request(path, htmx=True)
    request.user = run.requested_by if user is None else user
    return call_view(request, path)


def _text(response: HttpResponse) -> str:
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


def _confirm_recorded(stubs: tuple[StubModel, ...]) -> HttpResponse:
    path = "stubs/__actions/stub_recorded"
    data = {
        "mode": "keys",
        "keys": [str(stub.pk) for stub in stubs],
        "confirmed": "1",
        "expected_count": str(len(stubs)),
    }
    response = call_view(make_request(path, method="post", data=data, htmx=True), path)
    assert isinstance(response, HttpResponse)
    return response


@pytest.fixture
def two_stubs(mock_site_context: Site) -> tuple[StubModel, StubModel]:
    return make_stub(name="row-a"), make_stub(name="row-b")


@pytest.fixture(autouse=True)
def _clear_shown_log():
    StubRecordedBulkAction.shown.clear()
    yield
    StubRecordedBulkAction.shown.clear()


def test_confirming_a_recorded_action_above_the_threshold_queues_a_run_and_polls_it(
    two_stubs: tuple[StubModel, StubModel], settings
) -> None:
    settings.BULK_BACKGROUND_THRESHOLD = 1

    response = _confirm_recorded(two_stubs)

    run = BulkActionRun.objects.get()
    # The test task backend runs the queued task at once, so the run is
    # already done by the time the request answers.
    assert (response.status_code, run.status, run.scope) == (
        204,
        RunStatus.DONE,
        None,
    )
    assert run.action_path == RECORDED_PATH
    assert sorted(run.keys) == sorted(str(stub.pk) for stub in two_stubs)
    assert json.loads(response["HX-Trigger"])["bulkRunStarted"]["status_url"] == (
        f"/test-panel/framework/stubs/__runs/{run.pk}"
    )
    assert "2 stub models changed." in _text(_poll(run))


def test_a_recorded_run_records_the_sections_scope(
    two_stubs: tuple[StubModel, StubModel], settings
) -> None:
    settings.BULK_BACKGROUND_THRESHOLD = 1
    scope = make_stub(name="the-scope")
    RecordingCapabilityConfig.reset(scope=scope)

    _confirm_recorded(two_stubs)

    assert BulkActionRun.objects.get().scope == scope


def test_confirming_a_recorded_action_below_the_threshold_runs_it_inline(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    response = _confirm_recorded(two_stubs)

    run = BulkActionRun.objects.get()
    assert (response.status_code, run.status) == (200, RunStatus.DONE)
    assert "2 stub models changed." in _text(response)
    assert not StubModel.objects.filter(is_active=True).exists()


@pytest.mark.parametrize("status", [RunStatus.QUEUED, RunStatus.RUNNING])
def test_an_unfinished_run_answers_204(
    two_stubs: tuple[StubModel, StubModel], status: str
) -> None:
    run = _recorded_run(make_staff_user(), *two_stubs, status=status)

    response = _poll(run)

    assert (response.status_code, response.content) == (204, b"")
    assert StubRecordedBulkAction.shown == []


def test_a_finished_run_answers_the_result_modal_and_refreshes_the_table(
    two_stubs: tuple[StubModel, StubModel], mock_site_context: Site
) -> None:
    run = _recorded_run(make_staff_user(), *two_stubs)
    run_bulk_action(str(run.pk), mock_site_context.pk)

    response = _poll(run)

    assert response.status_code == 200
    assert "2 stub models changed." in _text(response)
    assert json.loads(response["HX-Trigger"]) == {"itemChanged": {"ids": []}}
    assert StubRecordedBulkAction.shown == [run.pk]


def test_a_failed_run_answers_a_modal_saying_where_it_stopped(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    run = _recorded_run(
        make_staff_user(),
        *two_stubs,
        status=RunStatus.FAILED,
        processed_count=1,
        error_message="Unexpected error.",
    )

    response = _poll(run)

    text = _text(response)
    assert "Stopped after 1 of 2 stub models." in text
    assert "Unexpected error." in text
    assert json.loads(response["HX-Trigger"]) == {"itemChanged": {"ids": []}}


def test_a_finished_run_of_a_removed_action_answers_its_summary(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    """The poll used to look the action up unguarded and 500 once it was
    renamed or removed."""
    run = _recorded_run(
        make_staff_user(),
        *two_stubs,
        action_path="nowhere.RenamedAway",
        action_name="renamed_away",
        status=RunStatus.DONE,
        result=BulkResult(
            counts=[BulkCount("changed", "", 2)], entries=[], left_out=0
        ).to_json(),
    )

    response = _poll(run)

    assert response.status_code == 200
    assert "Renamed away finished: 2 rows changed." in _text(response)


def test_a_run_is_a_404_for_another_user(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    run = _recorded_run(make_staff_user(), *two_stubs, status=RunStatus.DONE)

    response = _poll(run, user=make_staff_user())

    assert response.status_code == 404


def test_a_run_is_a_404_for_an_anonymous_visitor(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    run = _recorded_run(make_staff_user(), *two_stubs, status=RunStatus.DONE)

    response = _poll(run, user=AnonymousUser())

    assert response.status_code == 404


def test_a_run_of_another_scope_is_a_404(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    run = _recorded_run(
        make_staff_user(), *two_stubs, status=RunStatus.DONE, scope=make_stub()
    )

    response = _poll(run)

    assert response.status_code == 404


def test_a_run_of_another_table_is_a_404(
    two_stubs: tuple[StubModel, StubModel],
) -> None:
    run = _recorded_run(
        make_staff_user(), *two_stubs, status=RunStatus.DONE, table_key="elsewhere"
    )

    response = _poll(run)

    assert response.status_code == 404


def test_a_malformed_run_id_is_a_404_with_the_unavailable_fragment(
    mock_site_context: Site,
) -> None:
    path = "stubs/__runs/not-a-uuid"

    response = call_view(make_request(path, htmx=True), path)

    assert response.status_code == 404
    assert "no longer available" in _text(response).lower()


def test_a_runs_segment_that_is_not_last_is_a_404(mock_site_context: Site) -> None:
    path = f"stubs/__runs/{uuid.uuid4()}/__actions/stub_bulk"

    with pytest.raises(Http404):
        call_view(make_request(path), path)
