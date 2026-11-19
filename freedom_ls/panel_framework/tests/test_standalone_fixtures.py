import sys
from pathlib import Path

import pytest

from django.conf import settings

_STANDALONE_SETTINGS = "freedom_ls.panel_framework.tests.standalone_settings"


@pytest.mark.skipif(
    settings.SETTINGS_MODULE != _STANDALONE_SETTINGS,
    reason="only the standalone run is meant to load no other FLS module",
)
def test_standalone_run_loads_no_fls_module_but_the_framework():
    # Every test module is imported during collection, before any test runs,
    # so this covers them all whatever order the tests run in.
    framework = "freedom_ls.panel_framework"
    loaded_fls_modules = [
        name
        for name in sys.modules
        if name == "freedom_ls.conftest"
        or name.startswith("freedom_ls.tests")
        or (
            name.startswith("freedom_ls.")
            and name != framework
            and not name.startswith(f"{framework}.")
        )
    ]

    assert loaded_fls_modules == []


def test_no_stand_in_template_shadows_a_framework_template() -> None:
    tests_dir = Path(__file__).resolve().parent
    stand_ins = tests_dir / "standalone_templates"
    framework_templates = tests_dir.parent / "templates"

    shadowed = {
        path.relative_to(stand_ins) for path in stand_ins.rglob("*") if path.is_file()
    } & {
        path.relative_to(framework_templates)
        for path in framework_templates.rglob("*")
        if path.is_file()
    }

    assert shadowed == set()
