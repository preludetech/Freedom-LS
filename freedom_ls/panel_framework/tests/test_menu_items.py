"""Tests for _build_menu_items active highlighting."""

from __future__ import annotations

from freedom_ls.panel_framework.views import ListViewConfig, _build_menu_items


class CohortsConfig(ListViewConfig):
    url_name = "cohorts"
    menu_label = "Cohorts"


class StudentsConfig(ListViewConfig):
    url_name = "students"
    menu_label = "Students"


class CoursesConfig(ListViewConfig):
    url_name = "courses"
    menu_label = "Courses"


CONFIG: dict[str, type[ListViewConfig]] = {
    "cohorts": CohortsConfig,
    "students": StudentsConfig,
    "courses": CoursesConfig,
}

URL_NAME = "educator_interface:interface"


class TestBuildMenuItemsActive:
    def test_active_true_for_matching_section(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME, active_section="cohorts")
        active_items = [item for item in items if item["active"]]
        assert len(active_items) == 1
        assert active_items[0]["label"] == "Cohorts"

    def test_active_false_for_non_matching_sections(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME, active_section="cohorts")
        inactive_items = [item for item in items if not item["active"]]
        assert len(inactive_items) == 2
        labels = {item["label"] for item in inactive_items}
        assert labels == {"Students", "Courses"}

    def test_active_for_students_section(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME, active_section="students")
        by_label = {item["label"]: item for item in items}
        assert by_label["Students"]["active"] is True
        assert by_label["Cohorts"]["active"] is False
        assert by_label["Courses"]["active"] is False

    def test_empty_active_section_marks_nothing_active(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME, active_section="")
        assert all(item["active"] is False for item in items)

    def test_default_active_section_marks_nothing_active(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME)
        assert all(item["active"] is False for item in items)

    def test_nonexistent_section_marks_nothing_active(self) -> None:
        items = _build_menu_items(CONFIG, URL_NAME, active_section="nonexistent")
        assert all(item["active"] is False for item in items)
