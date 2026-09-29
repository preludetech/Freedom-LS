"""Tests for `config/settings_dev.py`'s database configuration.

No database access: these tests only read the settings dict Django already loaded.

The database's own `NAME` is read from the settings module directly, not from
`django.conf.settings`: once a database-backed test elsewhere in the suite has run,
Django's test runner overwrites `settings.DATABASES["default"]["NAME"]` in place with the
test database's name, so it no longer reflects the configured value.
"""

from __future__ import annotations

from typing import cast

from django.conf import settings

from config import settings_dev


def test_test_database_name_is_test_prefixed_db_name() -> None:
    test_config = cast("dict[str, str]", settings.DATABASES["default"]["TEST"])
    assert test_config["NAME"] == f"test_{settings_dev._db_name}"


def test_test_database_clones_from_template0() -> None:
    test_config = cast("dict[str, str]", settings.DATABASES["default"]["TEST"])
    assert test_config["TEMPLATE"] == "template0"
