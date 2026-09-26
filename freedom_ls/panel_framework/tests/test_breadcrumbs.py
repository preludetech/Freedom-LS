"""Tests for _build_breadcrumbs."""

from __future__ import annotations

import pytest

from django.http import HttpRequest

from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    ObjectViewConfig,
    _build_breadcrumbs,
)

from .conftest import StubModel, _make_stub
from .stub_panels import StubDataTablePanel


class CohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = StubModel


class UsersConfig(ListViewConfig):
    url_name = "users"
    menu_label = "Users"
    model = StubModel


class OrganisationConfig(ObjectViewConfig):
    url_name = "organisation"
    menu_label = "Organisation"
    instance_view = InstanceView

    @classmethod
    def get_object(cls, request: HttpRequest) -> StubModel:
        raise NotImplementedError


class DashboardConfig(BaseViewConfig):
    url_name = "dashboard"
    menu_label = "Dashboard"
    panel = StubDataTablePanel


SECTIONS = {
    "cohorts": CohortsConfig,
    "users": UsersConfig,
    "organisation": OrganisationConfig,
    "dashboard": DashboardConfig,
}

URL_NAME = "panel_framework_test:interface"


class TestBuildBreadcrumbs:
    def test_root_no_parts(self) -> None:
        assert _build_breadcrumbs([], SECTIONS, URL_NAME) == []

    def test_section_list_page(self) -> None:
        crumbs = _build_breadcrumbs(["cohorts"], SECTIONS, URL_NAME)

        assert crumbs == [{"label": "Cohorts"}]

    @pytest.mark.django_db
    def test_instance_page(self, mock_site_context: None) -> None:
        instance = _make_stub(name="Test Cohort")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            SECTIONS,
            URL_NAME,
            current_instance=instance,
        )

        assert crumbs == [
            {"label": "Cohorts", "url": "/test-panel/cohorts"},
            {"label": "Test Cohort"},
        ]

    def test_unknown_section_returns_empty(self) -> None:
        assert _build_breadcrumbs(["nonexistent"], SECTIONS, URL_NAME) == []

    @pytest.mark.django_db
    def test_extra_url_kwargs_merge_into_section_crumb_url(
        self, mock_site_context: None
    ) -> None:
        instance = _make_stub(name="Test Cohort")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            SECTIONS,
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
        instance = _make_stub(name="Tab Test")

        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk), "__tabs", "details"],
            SECTIONS,
            URL_NAME,
            current_instance=instance,
        )

        assert crumbs == [
            {"label": "Cohorts", "url": "/test-panel/cohorts"},
            {"label": "Tab Test"},
        ]

    @pytest.mark.django_db
    def test_object_view_is_its_section_alone(self, mock_site_context: None) -> None:
        instance = _make_stub(name="Acme")

        crumbs = _build_breadcrumbs(
            ["organisation"], SECTIONS, URL_NAME, current_instance=instance
        )

        assert crumbs == [{"label": "Organisation"}]

    def test_base_view_is_its_section_alone(self) -> None:
        crumbs = _build_breadcrumbs(["dashboard"], SECTIONS, URL_NAME)

        assert crumbs == [{"label": "Dashboard"}]
