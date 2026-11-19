"""The panel framework keeps its own copies of a few freedom_ls.base helpers,
because it must run without FLS. Each copy must stay identical to its
original, so a fix to one (a new CSV formula trigger, say) reaches both.
"""

from __future__ import annotations

import importlib.util
import inspect
import re
from pathlib import Path
from types import ModuleType

import pytest

import freedom_ls.panel_framework.templatetags.data_table_tags as framework_data_table_tags
from freedom_ls.base import app_settings as base_app_settings
from freedom_ls.base import csv_import as base_csv_import
from freedom_ls.base import csv_safety as base_csv_safety
from freedom_ls.base import date_display as base_date_display
from freedom_ls.base.templatetags import pagination_tags as base_pagination_tags
from freedom_ls.panel_framework import app_settings as framework_app_settings
from freedom_ls.panel_framework import csv_safety as framework_csv_safety
from freedom_ls.panel_framework import field_display as framework_field_display
from freedom_ls.tests import playwright_helpers as base_playwright_helpers

BASE_SCRIPT = (
    Path(base_app_settings.__file__).parent
    / "static"
    / "base"
    / "js"
    / "alpine-components.js"
)
FRAMEWORK_SCRIPT = (
    Path(framework_app_settings.__file__).parent
    / "static"
    / "panel_framework"
    / "js"
    / "alpine-components.js"
)

FRAMEWORK_PLAYWRIGHT_HELPERS_PATH = (
    Path(framework_app_settings.__file__).parent / "tests" / "playwright" / "helpers.py"
)


def _load_module_from_path(name: str, path: Path) -> ModuleType:
    """Import a file by path, for a module the framework keeps out of its public names."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


framework_playwright_helpers = _load_module_from_path(
    "framework_playwright_helpers", FRAMEWORK_PLAYWRIGHT_HELPERS_PATH
)

SAME_SOURCE = [
    (base_csv_safety.escape_csv_formula, framework_csv_safety.escape_csv_formula),
    (base_csv_import.EchoWriter, framework_csv_safety.EchoWriter),
    (base_app_settings.Setting, framework_app_settings.Setting),
    (base_app_settings.AppSettings, framework_app_settings.AppSettings),
    (
        base_pagination_tags.pagination_suffix,
        framework_data_table_tags.pagination_suffix,
    ),
    (
        base_playwright_helpers.assert_no_horizontal_overflow,
        framework_playwright_helpers.assert_no_horizontal_overflow,
    ),
]

SAME_VALUE = [
    (base_csv_safety, framework_csv_safety, "FORMULA_TRIGGERS"),
    (base_csv_safety, framework_csv_safety, "UTF8_BOM"),
    (base_csv_safety, framework_csv_safety, "_E164_PHONE_NUMBER"),
    (base_date_display, framework_field_display, "DATE_DISPLAY_FORMAT"),
    (base_date_display, framework_field_display, "DATETIME_DISPLAY_FORMAT"),
    (base_playwright_helpers, framework_playwright_helpers, "QA_VIEWPORTS"),
]


@pytest.mark.parametrize(
    ("original", "copy"),
    SAME_SOURCE,
    ids=[original.__qualname__ for original, _copy in SAME_SOURCE],
)
def test_a_copied_helper_has_its_originals_source(
    original: object, copy: object
) -> None:
    assert inspect.getsource(copy) == inspect.getsource(original), (
        f"{inspect.getsourcefile(copy)} and {inspect.getsourcefile(original)} "
        "have drifted: change both."
    )


@pytest.mark.parametrize(
    ("original_module", "copy_module", "name"),
    SAME_VALUE,
    ids=[name for _original, _copy, name in SAME_VALUE],
)
def test_a_copied_constant_has_its_originals_value(
    original_module: ModuleType, copy_module: ModuleType, name: str
) -> None:
    assert getattr(copy_module, name) == getattr(original_module, name), (
        f"{name} differs between {copy_module.__name__} and "
        f"{original_module.__name__}: change both."
    )


def _component_body(script: Path, name: str) -> str:
    """The source of an `Alpine.data(name, ...)` registration, up to its closing `}));`."""
    source = script.read_text()
    match = re.search(
        rf'^( *)Alpine\.data\("{name}", \(\) => \(\{{\n(.*?)^\1\}}\)\);$',
        source,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"{script} does not register {name}"
    return match.group(2)


def test_panel_dropdown_menu_has_the_body_of_dropdown_menu() -> None:
    assert _component_body(FRAMEWORK_SCRIPT, "panelDropdownMenu") == _component_body(
        BASE_SCRIPT, "dropdownMenu"
    ), "panelDropdownMenu and dropdownMenu have drifted: change both."
