"""Section kinds and panel-level behaviour, dispatched through the view."""

from __future__ import annotations

import pytest
from guardian.shortcuts import assign_perm

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse

from freedom_ls.panel_framework.actions import DeleteAction, PanelAction
from freedom_ls.panel_framework.panels import Panel, PanelStack
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    NavGroup,
    ObjectViewConfig,
    sections_by_url_name,
)

from .conftest import StubModel, _make_stub
from .stub_panels import StubBaseConfig, StubDataTablePanel, StubHiddenPanel
from .view_helpers import call_view, fetch, make_request

pytestmark = pytest.mark.django_db


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


class _FirstStubConfig(ObjectViewConfig):
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


DELETE_URL = "/test-panel/framework/first-stub/__panels/deletable/__actions/delete"
CONFIG = [NavGroup("Configs", [_FirstStubConfig, StubBaseConfig, _TenantBaseConfig])]


def _view(path_string: str, **request_kwargs: object):
    return call_view(make_request(path_string, **request_kwargs), path_string, CONFIG)


def test_an_object_view_renders_its_object_at_the_section_url(
    mock_site_context,
) -> None:
    _make_stub(name="alpha")

    html = _view("first-stub").content.decode()

    assert '<h1 id="instance-title">alpha</h1>' in html
    assert "<h2>Deletable</h2>" in html


def test_an_object_view_runs_check_access_on_its_object(mock_site_context) -> None:
    _make_stub(name="secret-alpha")

    with pytest.raises(Http404):
        _view("first-stub")


def test_a_base_view_renders_an_instance_free_table_panel(mock_site_context) -> None:
    _make_stub(name="row-in-base-view")

    html = fetch("stub-base").content.decode()

    assert "row-in-base-view" in html
    assert "<h2>Stub</h2>" in html
    assert 'id="instance-title"' not in html


def test_a_base_view_missing_a_required_request_attribute_404s(
    mock_site_context,
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


def test_a_hidden_panel_is_not_rendered(mock_site_context) -> None:
    _make_stub(name="alpha")

    html = _view("first-stub").content.decode()

    assert "<h2>Hidden</h2>" not in html


def test_a_hidden_panels_url_404s(mock_site_context) -> None:
    _make_stub(name="alpha")

    with pytest.raises(Http404):
        _view("first-stub/__panels/hidden")


def _as_a_user_who_may_delete(
    stub: StubModel, path_string: str, **request_kwargs: object
) -> HttpResponse:
    request = make_request(path_string, **request_kwargs)
    assign_perm("freedom_ls_panel_framework.delete_stubmodel", request.user, stub)
    return call_view(request, path_string, CONFIG)


def test_a_delete_action_from_a_panel_renders_its_trigger(mock_site_context) -> None:
    stub = _make_stub(name="alpha")

    html = _as_a_user_who_may_delete(stub, "first-stub").content.decode()

    assert f'hx-delete="{DELETE_URL}"' in html


def test_a_delete_action_from_a_panel_deletes_on_submit(mock_site_context) -> None:
    stub = _make_stub(name="alpha")
    path_string = DELETE_URL.removeprefix("/test-panel/framework/")

    response = _as_a_user_who_may_delete(stub, path_string, method="delete")

    assert response.status_code == 204
    assert response["HX-Redirect"] == "/deleted"
    assert not StubModel.objects.filter(pk=stub.pk).exists()
