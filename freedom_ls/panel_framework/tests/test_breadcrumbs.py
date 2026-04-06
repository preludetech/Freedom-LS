"""Tests for _build_breadcrumbs."""

from __future__ import annotations

import pytest

from freedom_ls.panel_framework.views import ListViewConfig, _build_breadcrumbs

from .conftest import StubModel


class CohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"
    model = StubModel


class UsersConfig(ListViewConfig):
    url_name = "users"
    menu_label = "Users"
    model = StubModel


CONFIG: dict[str, type[ListViewConfig]] = {
    "cohorts": CohortsConfig,
    "users": UsersConfig,
}

URL_NAME = "panel_framework_test:interface"


class TestBuildBreadcrumbs:
    def test_root_no_parts(self) -> None:
        crumbs = _build_breadcrumbs([], CONFIG, URL_NAME)
        assert crumbs == []

    def test_section_list_page(self) -> None:
        crumbs = _build_breadcrumbs(["cohorts"], CONFIG, URL_NAME)
        assert crumbs == [{"label": "Cohorts"}]

    @pytest.mark.django_db
    def test_instance_page(self, mock_site_context: None) -> None:
        instance = StubModel.objects.create(name="Test Cohort")
        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            CONFIG,
            URL_NAME,
            current_instance=instance,
        )
        assert crumbs == [
            {"label": "Cohorts", "url": "/test-panel/cohorts"},
            {"label": "Test Cohort"},
        ]

    def test_section_list_page_different_section(self) -> None:
        crumbs = _build_breadcrumbs(["users"], CONFIG, URL_NAME)
        assert crumbs == [{"label": "Users"}]
