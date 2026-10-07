"""Tests for _build_menu_items: groups, active highlighting, icons and counts."""

from __future__ import annotations

import pytest

from django.db.models import Model
from django.http import HttpRequest
from django.test import RequestFactory

from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    ListViewConfig,
    NavGroup,
    _build_menu_items,
)

from .conftest import _make_stub
from .stub_panels import StubDataTablePanel


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


CONFIG = [
    NavGroup("Teaching", [DashboardConfig, CohortsConfig]),
    NavGroup("People", [LearnersConfig]),
    NavGroup("Empty", []),
]

URL_NAME = "panel_framework_test:interface"


def _items(
    active_section: str = "", **kwargs: Model | dict[str, str] | None
) -> list[dict[str, object]]:
    groups = _build_menu_items(
        CONFIG, URL_NAME, RequestFactory().get("/"), active_section, **kwargs
    )
    return [item for group in groups for item in group["items"]]


def _by_label(
    active_section: str = "", **kwargs: Model | dict[str, str] | None
) -> dict[str, dict[str, object]]:
    return {item["label"]: item for item in _items(active_section, **kwargs)}


def test_one_group_per_nav_group_with_sections() -> None:
    groups = _build_menu_items(CONFIG, URL_NAME, RequestFactory().get("/"))

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
        CONFIG,
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
    items = _by_label("cohorts", current_instance=_make_stub(name="Ada"))

    assert items["Cohorts"]["aria_current"] == "true"
    assert items["Learners"]["aria_current"] == ""


@pytest.mark.django_db
def test_an_instance_page_adds_nothing_about_the_instance_to_the_menu(
    mock_site_context: None,
) -> None:
    groups = _build_menu_items(
        CONFIG,
        URL_NAME,
        RequestFactory().get("/"),
        "cohorts",
        current_instance=_make_stub(name="Ada"),
    )

    assert "Ada" not in str(groups)
