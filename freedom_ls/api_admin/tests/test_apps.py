"""Tests for the api_admin app config."""

from __future__ import annotations

import pytest

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.api_admin"):
    pytest.skip("api_admin not installed", allow_module_level=True)


def test_loading_the_models_without_api_says_what_to_install(monkeypatch):
    # Arrange
    app_config = apps.get_app_config("freedom_ls_api_admin")
    monkeypatch.setattr(apps, "is_installed", lambda name: name != "freedom_ls.api")

    # Act / Assert
    with pytest.raises(ImproperlyConfigured, match=r"requires freedom_ls\.api\."):
        app_config.import_models()
