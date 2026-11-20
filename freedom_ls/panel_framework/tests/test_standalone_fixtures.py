import sys

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
