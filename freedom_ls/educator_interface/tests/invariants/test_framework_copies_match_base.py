"""The panel framework keeps its own copies of a few freedom_ls.base helpers,
because it must run without FLS. Each copy must stay identical to its
original, so a fix to one (a new CSV formula trigger, say) reaches both.
"""

from __future__ import annotations

import inspect
from types import ModuleType

import pytest

from freedom_ls.base import app_settings as base_app_settings
from freedom_ls.base import csv_import as base_csv_import
from freedom_ls.base import csv_safety as base_csv_safety
from freedom_ls.base import date_display as base_date_display
from freedom_ls.panel_framework import app_settings as framework_app_settings
from freedom_ls.panel_framework import csv_safety as framework_csv_safety
from freedom_ls.panel_framework import field_display as framework_field_display

SAME_SOURCE = [
    (base_csv_safety.escape_csv_formula, framework_csv_safety.escape_csv_formula),
    (base_csv_import.EchoWriter, framework_csv_safety.EchoWriter),
    (base_app_settings.Setting, framework_app_settings.Setting),
    (base_app_settings.AppSettings, framework_app_settings.AppSettings),
]

SAME_VALUE = [
    (base_csv_safety, framework_csv_safety, "FORMULA_TRIGGERS"),
    (base_csv_safety, framework_csv_safety, "UTF8_BOM"),
    (base_csv_safety, framework_csv_safety, "_E164_PHONE_NUMBER"),
    (base_date_display, framework_field_display, "DATE_DISPLAY_FORMAT"),
    (base_date_display, framework_field_display, "DATETIME_DISPLAY_FORMAT"),
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
