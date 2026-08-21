"""Resolving __tabs/{tab}/__panels/{panel}, and InstanceDetailsPanel.

Both were previously reached only through a consumer app's smoke test, which
asserted status codes and nothing about what rendered.
"""

from __future__ import annotations

import pytest

from django.db.models import Model
from django.http import Http404, HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.panels import InstanceDetailsPanel
from freedom_ls.panel_framework.tabs import Tab
from freedom_ls.panel_framework.views import (
    InstanceView,
    ListViewConfig,
    panel_framework_view,
)

from .conftest import StubModel, _make_stub, _make_stub_child, make_staff_user


class StubDetailsPanel(InstanceDetailsPanel):
    title = "Stub Details"
    fields = ["name"]


class TabbedInstanceView(InstanceView):
    tabs = {
        "details": Tab(label="Details", panels={"details": StubDetailsPanel}),
    }


class TabbedConfig(ListViewConfig):
    """Declared here rather than added to the shared stubs: giving
    StubInstanceView tabs changes how it renders, which other modules assert
    on."""

    url_name = "tabbed"
    menu_label = "Tabbed"
    model = StubModel
    instance_view = TabbedInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        return None


CONFIG = {"tabbed": TabbedConfig}
TEMPLATE = "panel_framework/test_interface.html"
URL_NAME = "panel_framework_test:interface"


def _request(path: str):
    request = RequestFactory().get(path, HTTP_HX_REQUEST="true")
    request.user = make_staff_user()
    return request


def _fetch(path_string: str):
    return panel_framework_view(
        config=CONFIG,
        request=_request(f"/test-panel/{path_string}"),
        path_string=path_string,
        template_name=TEMPLATE,
        url_name=URL_NAME,
    )


@pytest.mark.django_db
class TestTabPanelFetch:
    def test_panel_inside_a_tab_renders_that_panels_content(self, mock_site_context):
        stub = _make_stub(name="Tabbed Stub")

        response = _fetch(f"tabbed/{stub.pk}/__tabs/details/__panels/details")

        assert response.status_code == 200
        assert "Tabbed Stub" in response.content.decode()

    def test_unknown_tab_name_404s(self, mock_site_context):
        stub = _make_stub(name="Tabbed Stub")

        with pytest.raises(Http404):
            _fetch(f"tabbed/{stub.pk}/__tabs/no-such-tab/__panels/details")

    def test_unknown_panel_name_inside_a_known_tab_404s(self, mock_site_context):
        stub = _make_stub(name="Tabbed Stub")

        with pytest.raises(Http404):
            _fetch(f"tabbed/{stub.pk}/__tabs/details/__panels/no-such-panel")

    def test_missing_tab_name_after_the_tabs_segment_404s(self, mock_site_context):
        stub = _make_stub(name="Tabbed Stub")

        with pytest.raises(Http404):
            _fetch(f"tabbed/{stub.pk}/__tabs")


@pytest.mark.django_db
class TestInstanceDetailsPanel:
    def test_renders_each_declared_field_with_its_verbose_name(self, mock_site_context):
        stub = _make_stub(name="Detailed Stub")

        content = StubDetailsPanel(stub).get_content(_request("/test-panel/"))

        assert "Name" in content
        assert "Detailed Stub" in content

    def test_dot_notation_field_traverses_the_related_object(self, mock_site_context):
        """A path like "user.email" resolves through the relation rather than
        looking for a literal "user.email" field."""

        class RelatedPanel(StubDetailsPanel):
            fields = ["parent.name"]

        child = _make_stub_child(_make_stub(name="Parent Stub"))

        content = RelatedPanel(child).get_content(_request("/test-panel/"))

        assert "Parent Stub" in content

    def test_dot_notation_through_a_non_relation_raises(self, mock_site_context):
        class BadPanel(StubDetailsPanel):
            fields = ["name.upper"]

        stub = _make_stub(name="Detailed Stub")

        with pytest.raises(ValueError, match="Expected Model at 'name'"):
            BadPanel(stub).get_content(_request("/test-panel/"))

    def test_no_edit_action_when_the_panel_is_not_editable(self, mock_site_context):
        stub = _make_stub(name="Detailed Stub")

        assert StubDetailsPanel(stub).get_actions(_request("/test-panel/")) == []
