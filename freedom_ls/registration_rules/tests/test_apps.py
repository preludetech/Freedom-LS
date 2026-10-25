"""Tests for the registration_rules app config."""

from __future__ import annotations

import pytest

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)


def test_loading_the_models_without_hr_attributes_says_what_to_install(monkeypatch):
    # Arrange
    app_config = apps.get_app_config("freedom_ls_registration_rules")
    monkeypatch.setattr(
        apps,
        "is_installed",
        lambda name: name != "freedom_ls.hr_attributes",
    )

    # Act / Assert
    with pytest.raises(
        ImproperlyConfigured, match=r"requires freedom_ls\.hr_attributes"
    ):
        app_config.import_models()


def test_loading_the_models_without_course_recommendations_says_what_to_install(
    monkeypatch,
):
    # Arrange
    app_config = apps.get_app_config("freedom_ls_registration_rules")
    monkeypatch.setattr(
        apps,
        "is_installed",
        lambda name: name != "freedom_ls.course_recommendations",
    )

    # Act / Assert
    with pytest.raises(
        ImproperlyConfigured, match=r"requires freedom_ls\.course_recommendations"
    ):
        app_config.import_models()
