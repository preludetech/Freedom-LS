"""Tests for the framework's default primitives, rendered through their <c-panel-*> names."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_django.fixtures

from django.core.paginator import Page, Paginator

from ..cotton_helpers import render_cotton


def _page(number: int) -> Page:
    return Paginator(list(range(30)), 10).page(number)


PRIMITIVE_DEFAULTS = [
    pytest.param(
        '<c-panel-chip variant="success" size="xs" data-testid="x">Active</c-panel-chip>',
        [
            "panel-chip",
            "panel-chip-success",
            "panel-chip-xs",
            'data-testid="x"',
            "Active",
        ],
        id="panel-chip",
    ),
    pytest.param(
        '<c-panel-button variant="error" size="small" data-testid="x">Delete</c-panel-button>',
        [
            "panel-btn",
            "panel-btn-error",
            "panel-btn-sm",
            'data-variant="error"',
            'data-testid="x"',
            "Delete",
        ],
        id="panel-button",
    ),
    pytest.param(
        '<c-panel-button-group variant="right" class="ms-auto">Go</c-panel-button-group>',
        ["flex justify-end", "ms-auto", "Go"],
        id="panel-button-group",
    ),
    pytest.param(
        '<c-panel-dropdown-menu aria_label="More" trigger_variant="ghost" trigger_size="small" '
        'panel_class="fixed w-64"><c-panel-button dropdown="true">Edit</c-panel-button>'
        "<c-panel-dropdown-menu-separator /></c-panel-dropdown-menu>",
        [
            'x-data="panelDropdownMenu"',
            "group/menu panel-btn panel-btn-ghost panel-btn-sm",
            'aria-label="More"',
            "fixed w-64",
            'role="separator"',
            "Edit",
        ],
        id="panel-dropdown-menu",
    ),
    pytest.param(
        '<c-panel-pagination :page_obj="page_obj" base_url="/t/" table_id="tbl" '
        'sort_by="name" page_param_name="p" />',
        [
            "panel-btn panel-btn-secondary panel-btn-sm",
            "panel-btn panel-btn-primary panel-btn-sm",
            'hx-get="/t/?p=1&amp;sort=name&amp;order=asc"',
            'hx-target="#tbl"',
            "Page 2 of 3",
        ],
        id="panel-pagination",
    ),
]

PRIMITIVE_OVERRIDES = [
    pytest.param("panel-chip", "<c-panel-chip>Hi</c-panel-chip>", id="panel-chip"),
    pytest.param(
        "panel-button", "<c-panel-button>Hi</c-panel-button>", id="panel-button"
    ),
    pytest.param(
        "panel-button-group",
        "<c-panel-button-group>Hi</c-panel-button-group>",
        id="panel-button-group",
    ),
    pytest.param(
        "panel-dropdown-menu",
        "<c-panel-dropdown-menu>Hi</c-panel-dropdown-menu>",
        id="panel-dropdown-menu",
    ),
    pytest.param(
        "panel-pagination",
        '<c-panel-pagination :page_obj="page_obj" />',
        id="panel-pagination",
    ),
    pytest.param(
        "panel-dropdown-menu-separator",
        "<c-panel-dropdown-menu-separator />",
        id="panel-dropdown-menu-separator",
    ),
]


@pytest.mark.parametrize(("source", "expected"), PRIMITIVE_DEFAULTS)
def test_a_primitive_renders_its_documented_props_and_slot(
    source: str, expected: list[str]
) -> None:
    html = render_cotton(source, page_obj=_page(2))

    assert {text for text in expected if text not in html} == set()


@pytest.mark.parametrize(
    ("source", "forbidden"),
    [
        pytest.param(
            "<c-panel-chip>Hi</c-panel-chip>",
            {"panel-chip-xs"},
            id="panel-chip-has-no-default-size",
        ),
        pytest.param(
            "<c-panel-button>Hi</c-panel-button>",
            {"panel-btn-sm", " disabled", "autofocus", "aria-label"},
            id="panel-button-has-no-default-size-or-flags",
        ),
        pytest.param(
            "<c-panel-dropdown-menu>Hi</c-panel-dropdown-menu>",
            {"panel-btn", "trigger_class"},
            id="panel-dropdown-menu-without-trigger-variant-has-no-button-class",
        ),
    ],
)
def test_a_primitive_omits_what_its_props_leave_unset(
    source: str, forbidden: set[str]
) -> None:
    html = render_cotton(source)

    assert {text for text in forbidden if text in html} == set()


@pytest.mark.parametrize(("name", "source"), PRIMITIVE_OVERRIDES)
def test_a_template_at_the_first_template_dir_replaces_a_primitive(
    name: str,
    source: str,
    tmp_path: Path,
    settings: pytest_django.fixtures.SettingsWrapper,
) -> None:
    (tmp_path / "cotton").mkdir()
    (tmp_path / "cotton" / f"{name}.html").write_text("<i>overridden</i>")
    settings.TEMPLATES[0]["DIRS"] = [str(tmp_path), *settings.TEMPLATES[0]["DIRS"]]

    html = render_cotton(source, page_obj=_page(2))

    assert "<i>overridden</i>" in html
