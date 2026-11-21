import sys
from pathlib import Path

import pytest

from django.conf import settings


@pytest.fixture
def standalone_run(request: pytest.FixtureRequest) -> None:
    """Skip unless pytest was started with the icons app's standalone ini file."""
    if request.config.inipath is None or (
        Path(request.config.inipath).name != "standalone_pytest.ini"
    ):
        pytest.skip("only meaningful under standalone_pytest.ini")


def test_the_standalone_run_uses_the_standalone_settings(standalone_run: None) -> None:
    assert settings.SETTINGS_MODULE == "freedom_ls.icons.tests.standalone_settings"


def test_the_standalone_run_loads_no_other_freedom_ls_module(
    standalone_run: None,
) -> None:
    foreign = [
        name
        for name in sys.modules
        if name.startswith("freedom_ls.")
        and name != "freedom_ls.icons"
        and not name.startswith("freedom_ls.icons.")
    ]

    assert foreign == []
