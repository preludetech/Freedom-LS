"""Tests for panels: binding, visibility, children and region ids, the section
kinds the view dispatches, instance details rows, tab dispatch and the menu built from the config."""

from __future__ import annotations

import json
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.actions import DeleteAction, PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.panels import (
    InstanceDetailsPanel,
    Panel,
    PanelStack,
    TabSet,
)
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    NavGroup,
    ObjectViewConfig,
    SectionConfigBase,
    _build_menu_items,
    sections_by_url_name,
)

from .helpers import make_stub, make_stub_child
from .stub_models import StubChild, StubModel
from .stub_panels import (
    RecordingCapabilityConfig,
    StubATablePanel,
    StubBaseConfig,
    StubBTablePanel,
    StubDataTablePanel,
    StubDetailsPanel,
    StubHiddenPanel,
    StubPairStack,
    StubTabSet,
)
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db


class _Stack(PanelStack):
    children = {"shown": StubDataTablePanel, "hidden": StubHiddenPanel}


class _AllHiddenTabs(TabSet):
    children = {"one": StubHiddenPanel, "two": StubHiddenPanel}


class _Tabs(TabSet):
    children = {"details": StubATablePanel, "details2": StubBTablePanel}


class _ModelPanel(Panel):
    model = StubModel


class _NarrowedTablePanel(StubDataTablePanel):
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).filter(name__startswith="keep")


class _GatedPanel(Panel):
    title = "Gated"
    capability = "freedom_ls_panel_framework.view_stubmodel"


class _GatedTabs(TabSet):
    children = {"open": StubDataTablePanel, "gated": _GatedPanel}


def _ctx(path: str = "/base", instance: StubModel | None = None) -> PanelContext:
    return PanelContext(
        request=RequestFactory().get(path),
        instance=instance,
        base_url="/base",
        name="",
        config=SectionConfigBase,
    )


def test_a_hidden_child_is_left_out_of_get_children() -> None:
    stack = _Stack(_ctx())

    assert [child.ctx.name for child in stack.get_children()] == ["shown"]


def test_a_hidden_childs_name_is_a_404() -> None:
    stack = _Stack(_ctx())

    with pytest.raises(Http404):
        stack.child("hidden")


def test_a_container_whose_children_are_all_hidden_is_hidden() -> None:
    assert _AllHiddenTabs(_ctx()).is_shown() is False


def test_a_container_with_a_shown_child_is_shown() -> None:
    assert _Stack(_ctx()).is_shown() is True


def test_children_get_their_own_url_and_name() -> None:
    (child,) = _Stack(_ctx()).get_children()

    assert child.ctx.base_url == "/base/__panels/shown"
    assert child.ctx.name == "shown"


def test_two_children_get_different_region_ids() -> None:
    first, second = _Tabs(_ctx()).get_children()

    assert first.region_id != second.region_id


def test_tab_set_reads_its_active_child_from_the_request_path() -> None:
    tabs = _Tabs(_ctx("/base/__tabs/details2"))

    assert tabs.get_active_child().ctx.name == "details2"


def test_a_tab_does_not_claim_a_longer_tab_name_that_starts_with_it() -> None:
    tabs = _Tabs(_ctx("/base/__tabs/details2/__panels/x"))

    assert tabs.get_active_child().ctx.name == "details2"


def test_tab_set_falls_back_to_its_first_shown_child() -> None:
    tabs = _Tabs(_ctx("/base"))

    assert tabs.get_active_child().ctx.name == "details"


def test_a_panel_declaring_a_model_refuses_to_bind_without_an_instance() -> None:
    with pytest.raises(ImproperlyConfigured):
        _ModelPanel(_ctx())


def test_a_panel_without_a_model_binds_without_an_instance() -> None:
    assert StubDetailsPanel(_ctx()).instance is None


@pytest.mark.django_db
def test_a_get_queryset_override_narrows_the_rows(mock_site_context: Site) -> None:
    make_stub(name="keep-me")
    make_stub(name="drop-me")

    context = _NarrowedTablePanel(_ctx()).get_context_data()

    assert [row["object"].name for row in context["rows"]] == ["keep-me"]


@pytest.mark.django_db
def test_a_panel_whose_capability_is_denied_is_left_out_of_its_container(
    mock_site_context: Site,
) -> None:
    instance = make_stub()
    RecordingCapabilityConfig.reset(answer=False)
    ctx = PanelContext(
        request=RequestFactory().get("/base"),
        instance=instance,
        base_url="/base",
        name="",
        config=RecordingCapabilityConfig,
    )

    assert [child.ctx.name for child in _GatedTabs(ctx).get_children()] == ["open"]


@pytest.mark.django_db
def test_a_panel_whose_capability_is_denied_404s_at_its_own_url(
    mock_site_context: Site,
) -> None:
    instance = make_stub()
    RecordingCapabilityConfig.reset(answer=False)
    ctx = PanelContext(
        request=RequestFactory().get("/base"),
        instance=instance,
        base_url="/base",
        name="",
        config=RecordingCapabilityConfig,
    )

    with pytest.raises(Http404):
        _GatedTabs(ctx).child("gated")


@pytest.mark.django_db
def test_a_panel_whose_capability_is_granted_renders_and_is_asked_about_the_instance(
    mock_site_context: Site,
) -> None:
    instance = make_stub()
    RecordingCapabilityConfig.reset(answer=True)
    ctx = PanelContext(
        request=RequestFactory().get("/base"),
        instance=instance,
        base_url="/base",
        name="",
        config=RecordingCapabilityConfig,
    )

    gated = _GatedTabs(ctx).child("gated")

    assert gated.ctx.name == "gated"
    assert RecordingCapabilityConfig.asked == [(_GatedPanel.capability, instance)]


def test_page_url_advances_through_tabs_not_stacks() -> None:
    tabs = StubTabSet(_ctx())

    pair = next(child for child in tabs.get_children() if child.ctx.name == "pair")
    assert isinstance(pair, StubPairStack)
    # A tab's page_url is its own base_url: the address bar advances here.
    assert pair.ctx.page_url == pair.ctx.base_url

    a_child = next(child for child in pair.get_children() if child.ctx.name == "a")
    # A stack child shares its parent's page_url rather than getting its own.
    assert a_child.ctx.page_url == pair.ctx.page_url
    assert a_child.ctx.page_url != a_child.ctx.base_url


# Section kinds and panel-level behaviour, dispatched through the view.


class _DeletablePanel(Panel):
    title = "Deletable"

    def get_actions(self) -> list[PanelAction]:
        return [DeleteAction(success_url="/deleted")]


class _PanelsWithAHiddenOne(PanelStack):
    children = {
        "deletable": _DeletablePanel,
        "hidden": StubHiddenPanel,
    }


class _ObjectInstanceView(InstanceView):
    panel = _PanelsWithAHiddenOne


class _FirstStubConfig(RecordingCapabilityConfig, ObjectViewConfig):
    """Shows whichever stub sorts first by name."""

    url_name = "first-stub"
    menu_label = "First stub"
    instance_view = _ObjectInstanceView

    @classmethod
    def get_object(cls, request: HttpRequest) -> Model:
        first: Model = StubModel.objects.order_by("name")[0]
        return first

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        if instance.name.startswith("secret"):
            raise Http404


class _TenantBaseConfig(BaseViewConfig):
    url_name = "tenant-base"
    menu_label = "Tenant base"
    panel = StubDataTablePanel
    required_request_attrs = ("tenant",)


class _TenantRequest(HttpRequest):
    tenant: str


class _TenantObjectConfig(ObjectViewConfig):
    """Finds its object through a required request attribute."""

    url_name = "tenant-object"
    menu_label = "Tenant object"
    instance_view = _ObjectInstanceView
    required_request_attrs = ("tenant",)

    @classmethod
    def get_object(cls, request: HttpRequest) -> Model:
        found: Model = StubModel.objects.get(name=cast(_TenantRequest, request).tenant)
        return found


DELETE_URL = "/test-panel/framework/first-stub/__panels/deletable/__actions/delete"
SECTIONS_CONFIG = [
    NavGroup(
        "Configs",
        [_FirstStubConfig, StubBaseConfig, _TenantBaseConfig, _TenantObjectConfig],
    )
]


def _view(
    path_string: str, **request_kwargs: object
) -> HttpResponse | StreamingHttpResponse:
    return call_view(
        make_request(path_string, **request_kwargs), path_string, SECTIONS_CONFIG
    )


def test_an_object_view_renders_its_object_at_the_section_url(
    mock_site_context: Site,
) -> None:
    make_stub(name="alpha")

    html = _view("first-stub").content.decode()

    assert '<h1 id="instance-title">alpha</h1>' in html
    assert ">Deletable</h2>" in html


def test_an_object_view_runs_check_access_on_its_object(
    mock_site_context: Site,
) -> None:
    make_stub(name="secret-alpha")

    with pytest.raises(Http404):
        _view("first-stub")


def test_a_base_view_renders_an_instance_free_table_panel(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-in-base-view")

    html = fetch("stub-base").content.decode()

    assert "row-in-base-view" in html
    assert ">Stub</h2>" in html
    assert 'id="instance-title"' not in html


def test_a_list_view_renders_exactly_one_h1_with_the_section_heading(
    mock_site_context: Site,
) -> None:
    make_stub(name="row-in-list-view")

    html = fetch("stubs").content.decode()

    assert html.count("<h1") == 1
    assert "<h1>Stubs</h1>" in html


def test_a_base_view_renders_exactly_one_h1_with_the_section_heading(
    mock_site_context: Site,
) -> None:
    html = fetch("stub-base").content.decode()

    assert html.count("<h1") == 1
    assert "<h1>Stub base</h1>" in html


def test_a_base_view_missing_a_required_request_attribute_404s(
    mock_site_context: Site,
) -> None:
    with pytest.raises(Http404):
        _view("tenant-base")


def test_a_duplicate_url_name_is_improperly_configured() -> None:
    config = [
        NavGroup("One", [StubBaseConfig]),
        NavGroup("Two", [StubBaseConfig]),
    ]

    with pytest.raises(ImproperlyConfigured):
        sections_by_url_name(config)


def test_a_hidden_panel_is_not_rendered(mock_site_context: Site) -> None:
    make_stub(name="alpha")

    html = _view("first-stub").content.decode()

    assert ">Hidden</h2>" not in html


def test_a_hidden_panels_url_404s(mock_site_context: Site) -> None:
    make_stub(name="alpha")

    with pytest.raises(Http404):
        _view("first-stub/__panels/hidden")


def _as_a_user_permitted_to_delete(
    path_string: str, **request_kwargs: object
) -> HttpResponse | StreamingHttpResponse:
    """The recording stub config answers has_capability True, standing in for
    a role grant _FirstStubConfig would otherwise ask about."""
    RecordingCapabilityConfig.reset(answer=True)
    request = make_request(path_string, **request_kwargs)
    return call_view(request, path_string, SECTIONS_CONFIG)


def test_a_delete_action_from_a_panel_renders_its_trigger(
    mock_site_context: Site,
) -> None:
    make_stub(name="alpha")

    html = _as_a_user_permitted_to_delete("first-stub").content.decode()

    assert f'hx-get="{DELETE_URL}"' in html


def test_a_delete_actions_trigger_url_returns_its_confirmation_fragment(
    mock_site_context: Site,
) -> None:
    make_stub(name="alpha")
    path_string = DELETE_URL.removeprefix("/test-panel/framework/")

    html = _as_a_user_permitted_to_delete(path_string).content.decode()

    assert f'hx-delete="{DELETE_URL}"' in html


def test_a_delete_action_from_a_panel_deletes_on_submit(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="alpha")
    path_string = DELETE_URL.removeprefix("/test-panel/framework/")

    response = _as_a_user_permitted_to_delete(path_string, method="delete")

    assert response.status_code == 204
    assert json.loads(response["HX-Location"]) == {
        "path": "/deleted",
        "target": "#main-content",
        "swap": "outerHTML",
    }
    assert "HX-Redirect" not in response
    assert not StubModel.objects.filter(pk=stub.pk).exists()


def test_an_object_view_missing_a_required_request_attribute_404s_before_get_object(
    mock_site_context: Site,
) -> None:
    with pytest.raises(Http404):
        _view("tenant-object")


# InstanceDetailsPanel rows: labels, values and the edit action.


class StubInstanceDetails(InstanceDetailsPanel):
    model = StubModel
    fields = ["name", "kind", "is_active", "sat_score"]


class StubChildDetails(InstanceDetailsPanel):
    model = StubChild
    fields = ["parent__name"]


def _bind_details(
    panel_class: type[InstanceDetailsPanel], instance: Model
) -> InstanceDetailsPanel:
    return panel_class(
        PanelContext(
            request=RequestFactory().get("/"),
            instance=instance,
            base_url="/x",
            name="details",
            config=SectionConfigBase,
        )
    )


@pytest.mark.django_db
def test_rows_carry_label_value_and_is_boolean(mock_site_context: Site) -> None:
    stub = make_stub(name="Detailed", kind="b", is_active=True)

    rows = _bind_details(StubInstanceDetails, stub).get_rows()

    assert rows == [
        {"label": "name", "value": "Detailed", "is_boolean": False},
        {"label": "kind", "value": "Beta", "is_boolean": False},
        {"label": "is active", "value": True, "is_boolean": True},
        {"label": "SAT score", "value": "-", "is_boolean": False},
    ]


@pytest.mark.django_db
def test_a_dunder_path_resolves_through_the_relation(mock_site_context: Site) -> None:
    child = make_stub_child(make_stub(name="Parent Stub"))

    (row,) = _bind_details(StubChildDetails, child).get_rows()

    assert row["value"] == "Parent Stub"


@pytest.mark.django_db
def test_the_template_capitalises_the_label_once(mock_site_context: Site) -> None:
    stub = make_stub(name="Detailed")
    panel = _bind_details(StubInstanceDetails, stub)

    html = render_to_string(panel.template_name, panel.get_context_data())

    assert "Is active" in html
    assert "SAT score" in html
    assert "Sat Score" not in html


@pytest.mark.django_db
def test_no_edit_action_when_the_panel_is_not_editable(mock_site_context: Site) -> None:
    stub = make_stub(name="Detailed")

    assert _bind_details(StubInstanceDetails, stub).get_actions() == []


@pytest.mark.django_db
def test_the_template_renders_one_dl_with_a_dt_dd_pair_per_field_and_no_table(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Detailed", kind="b", is_active=True)
    panel = _bind_details(StubInstanceDetails, stub)

    html = render_to_string(panel.template_name, panel.get_context_data())

    row_count = len(panel.get_rows())
    assert html.count("<dl") == 1
    assert html.count("<dt") == row_count
    assert html.count("<dd") == row_count
    assert "<table" not in html


@pytest.mark.django_db
def test_a_boolean_field_still_renders_the_boolean_icon(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Detailed", is_active=True)
    panel = _bind_details(StubInstanceDetails, stub)

    html = render_to_string(panel.template_name, panel.get_context_data())

    assert 'aria-label="boolean_true"' in html


# Tab dispatch: every tab has a URL that renders the full page, and a tab
# click swaps only that tab's content.


def _tab_links(html: str) -> dict[str, lxml.html.HtmlElement]:
    document = lxml.html.fromstring(html)
    return {
        link.text_content().strip(): link
        for link in document.cssselect("nav[aria-label='Stub sections'] a")
    }


def _tab_region_id(stub_pk: object) -> str:
    html = fetch(f"stubs/{stub_pk}").content.decode()
    (region,) = lxml.html.fromstring(html).cssselect("[data-tab-set]")
    return str(region.get("id"))


def test_the_instance_url_shows_the_first_tab_as_current(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Tabbed Stub")

    links = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())

    assert links["Stub"].get("aria-current") == "page"
    assert links["Details"].get("aria-current") is None


def test_a_hidden_tab_has_no_link(mock_site_context: Site) -> None:
    stub = make_stub(name="Tabbed Stub")

    links = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())

    assert set(links) == {"Stub", "Details", "Pair", "Children", "Cards", "Sort only"}


def test_a_plain_get_of_a_tab_url_renders_the_full_page_with_that_tab_current(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Tabbed Stub")

    response = fetch(f"stubs/{stub.pk}/__tabs/details")

    html = response.content.decode()
    assert 'id="sidebar-nav"' in html
    assert _tab_links(html)["Details"].get("aria-current") == "page"
    assert "<p data-stub-details>Tabbed Stub</p>" in html


def test_tab_links_push_their_own_url_into_the_tab_region(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Tabbed Stub")
    region_id = _tab_region_id(stub.pk)

    link = _tab_links(fetch(f"stubs/{stub.pk}").content.decode())["Details"]

    url = f"/test-panel/framework/stubs/{stub.pk}/__tabs/details"
    assert link.get("href") == url
    assert link.get("hx-get") == url
    assert link.get("hx-target") == f"#{region_id}"
    assert link.get("hx-push-url") == "true"


def test_a_tab_click_returns_that_tab_and_an_announcement(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Tabbed Stub")

    response = fetch(
        f"stubs/{stub.pk}/__tabs/details",
        htmx=True,
        hx_target=_tab_region_id(stub.pk),
    )

    html = response.content.decode()
    assert "<p data-stub-details>Tabbed Stub</p>" in html
    assert 'hx-swap-oob="innerHTML:#scope-announcer"' in html
    assert "Showing Details" in html
    assert 'id="sidebar-nav"' not in html
    assert "<nav" not in html


def test_a_history_restore_of_a_tab_url_returns_the_full_page(
    mock_site_context: Site,
) -> None:
    stub = make_stub(name="Tabbed Stub")

    response = fetch(f"stubs/{stub.pk}/__tabs/details", htmx=True, restore=True)

    html = response.content.decode()
    assert 'id="sidebar-nav"' in html
    assert _tab_links(html)["Details"].get("aria-current") == "page"


def test_a_panel_inside_a_tab_renders_that_panel(mock_site_context: Site) -> None:
    stub = make_stub(name="row-in-tab")

    response = fetch(f"stubs/{stub.pk}/__tabs/default")

    assert "row-in-tab" in response.content.decode()


@pytest.mark.parametrize(
    "suffix",
    ["__tabs/hidden", "__tabs/no-such-tab", "__tabs", "__panels/default"],
    ids=["hidden tab", "unknown tab", "missing tab name", "wrong child segment"],
)
def test_unreachable_tab_paths_404(mock_site_context: Site, suffix: str) -> None:
    stub = make_stub(name="Tabbed Stub")

    with pytest.raises(Http404):
        fetch(f"stubs/{stub.pk}/{suffix}")


# Tests for _build_menu_items: groups, active highlighting, icons and counts.


class CohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    icon = "cohort"

    @classmethod
    def get_menu_count(cls, request: HttpRequest) -> int | None:
        return 7


class LearnersConfig(ListViewConfig):
    url_name = "learners"
    menu_label = "Learners"


class DashboardConfig(BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    panel = StubDataTablePanel


MENU_CONFIG = [
    NavGroup("Teaching", [DashboardConfig, CohortsConfig]),
    NavGroup("People", [LearnersConfig]),
    NavGroup("Empty", []),
]

MENU_URL_NAME = "panel_framework_test:interface"


def _items(
    active_section: str = "", **kwargs: Model | dict[str, str] | None
) -> list[dict[str, object]]:
    groups = _build_menu_items(
        MENU_CONFIG, MENU_URL_NAME, RequestFactory().get("/"), active_section, **kwargs
    )
    return [item for group in groups for item in group["items"]]


def _by_label(
    active_section: str = "", **kwargs: Model | dict[str, str] | None
) -> dict[str, dict[str, object]]:
    return {item["label"]: item for item in _items(active_section, **kwargs)}


def test_one_group_per_nav_group_with_sections() -> None:
    groups = _build_menu_items(MENU_CONFIG, MENU_URL_NAME, RequestFactory().get("/"))

    assert [group["heading"] for group in groups] == ["Teaching", "People"]


def test_items_keep_their_group_order() -> None:
    assert [item["label"] for item in _items()] == ["Dashboard", "Cohorts", "Learners"]


def test_only_the_matching_section_is_active() -> None:
    items = _by_label("learners")

    assert items["Learners"]["active"] is True
    assert items["Cohorts"]["active"] is False
    assert items["Dashboard"]["active"] is False


def test_no_active_section_marks_nothing_active() -> None:
    assert all(item["active"] is False for item in _items())


def test_an_unknown_section_marks_nothing_active() -> None:
    assert all(item["active"] is False for item in _items("nonexistent"))


def test_an_item_carries_its_icon_and_count() -> None:
    items = _by_label()

    assert items["Cohorts"]["icon"] == "cohort"
    assert items["Cohorts"]["count"] == 7
    assert items["Learners"]["count"] is None


def test_extra_url_kwargs_merge_into_section_url() -> None:
    groups = _build_menu_items(
        MENU_CONFIG,
        "panel_framework_test:scoped_interface",
        RequestFactory().get("/"),
        "cohorts",
        extra_url_kwargs={"extra": "acme"},
    )

    cohorts = next(i for g in groups for i in g["items"] if i["label"] == "Cohorts")
    assert cohorts["url"] == "/test-panel/scoped/acme/cohorts"


def test_the_active_section_is_the_current_page_on_its_own_list() -> None:
    items = _by_label("cohorts")

    assert items["Cohorts"]["aria_current"] == "page"
    assert items["Learners"]["aria_current"] == ""
    assert items["Dashboard"]["aria_current"] == ""


@pytest.mark.django_db
def test_on_an_instance_page_its_section_stays_current_but_not_as_the_page(
    mock_site_context: None,
) -> None:
    items = _by_label("cohorts", current_instance=make_stub(name="Ada"))

    assert items["Cohorts"]["aria_current"] == "true"
    assert items["Learners"]["aria_current"] == ""


@pytest.mark.django_db
def test_an_instance_page_adds_nothing_about_the_instance_to_the_menu(
    mock_site_context: None,
) -> None:
    groups = _build_menu_items(
        MENU_CONFIG,
        MENU_URL_NAME,
        RequestFactory().get("/"),
        "cohorts",
        current_instance=make_stub(name="Ada"),
    )

    assert "Ada" not in str(groups)
