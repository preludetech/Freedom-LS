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

URL_NAME = "educator_interface:interface"


class TestBuildBreadcrumbs:
    def test_root_no_parts_with_label(self) -> None:
        crumbs = _build_breadcrumbs([], CONFIG, URL_NAME, root_label="Educator")
        assert len(crumbs) == 1
        assert crumbs[0]["label"] == "Educator"
        assert "url" not in crumbs[0]

    def test_root_no_parts_without_label(self) -> None:
        crumbs = _build_breadcrumbs([], CONFIG, URL_NAME, root_label="")
        assert crumbs == []

    def test_section_list_page(self) -> None:
        crumbs = _build_breadcrumbs(
            ["cohorts"], CONFIG, URL_NAME, root_label="Educator"
        )
        assert len(crumbs) == 2
        assert crumbs[0]["label"] == "Educator"
        assert "url" in crumbs[0]
        assert crumbs[1]["label"] == "Cohorts"
        assert "url" not in crumbs[1]

    @pytest.mark.django_db
    def test_instance_page(self, mock_site_context: None) -> None:
        instance = StubModel.objects.create(name="Test Cohort")
        crumbs = _build_breadcrumbs(
            ["cohorts", str(instance.pk)],
            CONFIG,
            URL_NAME,
            current_instance=instance,
            root_label="Educator",
        )
        assert len(crumbs) == 3
        assert crumbs[0]["label"] == "Educator"
        assert "url" in crumbs[0]
        assert crumbs[1]["label"] == "Cohorts"
        assert "url" in crumbs[1]
        assert crumbs[2]["label"] == "Test Cohort"
        assert "url" not in crumbs[2]

    def test_empty_root_label_skips_root(self) -> None:
        crumbs = _build_breadcrumbs(["cohorts"], CONFIG, URL_NAME, root_label="")
        assert crumbs == []

    def test_section_list_page_different_section(self) -> None:
        crumbs = _build_breadcrumbs(["users"], CONFIG, URL_NAME, root_label="Educator")
        assert len(crumbs) == 2
        assert crumbs[1]["label"] == "Users"
        assert "url" not in crumbs[1]
