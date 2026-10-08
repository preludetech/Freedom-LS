"""Tests for `config/settings_dev.py`'s database configuration.

No database access: these tests only read the settings dict Django already loaded.

`django.conf.settings` wraps a `Settings` object whose dict/list attributes are the very
same objects `config/settings_dev.py` built, not copies. Under `pytest -n`, pytest-django
appends an xdist worker suffix to `settings.DATABASES["default"]["TEST"]["NAME"]` in
place, so that mutation is visible on `config.settings_dev`'s own module too, not just on
`django.conf.settings`. Anything built from the worker-specific database name -- the test
database name itself, and `application_name` -- is read from a freshly executed copy of
the settings file instead, so a worker's mutation of the live settings object never
reaches these assertions.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType
from typing import cast

import pytest

from django.conf import settings

from config import settings_dev
from config.settings_dev import build_application_name
from freedom_ls.base.git_utils import branch_to_db_name

pytestmark = pytest.mark.dev_tooling


def _load_pristine_settings_dev() -> ModuleType:
    """Execute `config/settings_dev.py` fresh, into its own module object."""
    spec = importlib.util.spec_from_file_location(
        "config._settings_dev_pristine", settings_dev.__file__
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_test_database_name_is_test_prefixed_db_name() -> None:
    pristine = _load_pristine_settings_dev()
    test_config = cast("dict[str, str]", pristine.DATABASES["default"]["TEST"])
    assert test_config["NAME"] == f"test_{pristine._db_name}"


def test_test_database_clones_from_template0() -> None:
    test_config = cast("dict[str, str]", settings.DATABASES["default"]["TEST"])
    assert test_config["TEMPLATE"] == "template0"


def test_app_connects_as_the_non_superuser_role() -> None:
    assert settings.DATABASES["default"]["USER"] == "fls_dev"


def test_application_name_starts_with_pytest() -> None:
    pristine = _load_pristine_settings_dev()
    options = cast("dict[str, str]", pristine.DATABASES["default"]["OPTIONS"])
    assert options["application_name"].startswith("pytest:")


def test_build_application_name_for_test_worker_truncates_to_63_chars() -> None:
    db_name = branch_to_db_name("a" * 50)

    name = build_application_name(
        testing=True, argv=["pytest"], worker="gw3", db_name=db_name
    )

    assert name.startswith("pytest:gw3:db_")
    assert len(name) == 63


def test_build_application_name_for_manage_py_uses_subcommand() -> None:
    name = build_application_name(
        testing=False, argv=["manage.py", "runserver"], worker=None, db_name="db_x"
    )

    assert name == "runserver:-:db_x"


def test_build_application_name_for_non_manage_py_entrypoint_is_django() -> None:
    name = build_application_name(
        testing=False, argv=["gunicorn"], worker=None, db_name="db_x"
    )

    assert name == "django:-:db_x"
