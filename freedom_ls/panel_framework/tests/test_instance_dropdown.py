"""Tests for sidebar instance dropdown in _build_menu_items."""

from __future__ import annotations

import pytest

from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.views import (
    InstanceView,
    ListViewConfig,
    NavGroup,
    _build_menu_items,
    panel_framework_view,
)

from .conftest import StubModel, _make_stub, make_staff_user
from .stub_panels import StubDetailsPanel


class CohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"


class LearnersConfig(ListViewConfig):
    url_name = "learners"
    menu_label = "Learners"


CONFIG = [NavGroup("Sections", [CohortsConfig, LearnersConfig])]

URL_NAME = "panel_framework_test:interface"


def _menu_items(
    active_section: str = "", current_instance: StubModel | None = None
) -> list[dict[str, object]]:
    groups = _build_menu_items(
        CONFIG,
        URL_NAME,
        RequestFactory().get("/"),
        active_section=active_section,
        current_instance=current_instance,
    )
    return [item for group in groups for item in group["items"]]


class TestBuildMenuItemsInstanceDropdown:
    def test_expanded_true_when_instance_provided_and_section_matches(self) -> None:
        instance = StubModel(pk=1, name="Test Cohort")
        items = _menu_items("cohorts", instance)
        cohorts_item = next(i for i in items if i["label"] == "Cohorts")
        assert cohorts_item["expanded"] is True
        assert cohorts_item["instance_label"] == "Test Cohort"
        assert "cohorts/1" in str(cohorts_item["instance_url"])

    def test_expanded_false_on_list_page_no_instance(self) -> None:
        items = _menu_items("cohorts")
        cohorts_item = next(i for i in items if i["label"] == "Cohorts")
        assert cohorts_item["expanded"] is False
        assert cohorts_item["instance_label"] == ""
        assert cohorts_item["instance_url"] == ""

    def test_instance_data_only_for_active_section(self) -> None:
        instance = StubModel(pk=1, name="Test Cohort")
        items = _menu_items("cohorts", instance)
        learners_item = next(i for i in items if i["label"] == "Learners")
        assert learners_item["expanded"] is False
        assert learners_item["instance_label"] == ""
        assert learners_item["instance_url"] == ""

    def test_expanded_false_when_no_active_section(self) -> None:
        instance = StubModel(pk=1, name="Test Cohort")
        items = _menu_items("", instance)
        assert all(item["expanded"] is False for item in items)
        assert all(item["instance_label"] == "" for item in items)


class StubInstanceView(InstanceView):
    panel = StubDetailsPanel


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


class StubListConfigWithModel(ListViewConfig):
    url_name = "stubs"
    menu_label = "Stubs"
    model = StubModel
    instance_view = StubInstanceView
    list_view = StubDataTable

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        # This config goes through the base get_instance_view for real, so it
        # inherits deny-by-default. Permissive here because this test exercises
        # OOB sidebar rendering, not authorisation rules.
        return None


FULL_CONFIG = [NavGroup("Stubs", [StubListConfigWithModel])]

TEMPLATE = "panel_framework/test_interface.html"


@pytest.mark.django_db
class TestOobSidebarWithInstance:
    def test_oob_sidebar_contains_instance_data(self, mock_site_context: None) -> None:
        """OOB sidebar fragment includes instance label when navigating to instance."""
        stub = _make_stub(name="My Stub Instance")
        factory = RequestFactory()
        request = factory.get(
            f"/test-panel/stubs/{stub.pk}",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="main-content",
        )
        request.user = make_staff_user()
        response = panel_framework_view(
            config=FULL_CONFIG,
            request=request,
            path_string=f"stubs/{stub.pk}",
            template_name=TEMPLATE,
            url_name=URL_NAME,
        )
        content = response.content.decode()
        assert 'id="sidebar-nav"' in content
        assert "My Stub Instance" in content
        assert f"stubs/{stub.pk}" in content
