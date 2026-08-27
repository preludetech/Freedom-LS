from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.test import override_settings

from freedom_ls.base.storage import storage_for_alias


@override_settings(
    STORAGES={"reports": {"BACKEND": "django.core.files.storage.FileSystemStorage"}}
)
def test_a_declared_alias_returns_its_storage() -> None:
    assert isinstance(
        storage_for_alias("reports", "REPORTS_STORAGE_ALIAS"), FileSystemStorage
    )


@override_settings(
    STORAGES={"reports": {"BACKEND": "django.core.files.storage.FileSystemStorage"}}
)
def test_an_undeclared_alias_names_itself_and_the_setting_that_chose_it() -> None:
    """Django's own InvalidStorageError names neither, and it surfaces as a bare
    traceback while the app registry imports the model — the one moment an
    operator has the least context to work out what went wrong."""
    with pytest.raises(ImproperlyConfigured) as excinfo:
        storage_for_alias("generated_reports", "REPORTS_STORAGE_ALIAS")

    message = str(excinfo.value)
    assert "generated_reports" in message
    assert "REPORTS_STORAGE_ALIAS" in message
