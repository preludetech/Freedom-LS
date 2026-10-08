"""System checks for the comms app."""

from __future__ import annotations

from django.test import override_settings

from freedom_ls.base.notification_categories import NotificationCategory
from freedom_ls.comms.checks import (
    check_messaging_policy_app_installed,
    check_messaging_policy_imports,
    check_notification_category_keys_are_unique,
    check_notification_delivery_backends_import,
)


def test_duplicate_category_keys_produce_an_error() -> None:
    duplicate = NotificationCategory(
        key="course.registered",
        label="Course registration",
        icon="course",
        message="You've been registered for %(course_title)s",
        url_builder=None,
    )

    with override_settings(NOTIFICATION_CATEGORIES=[duplicate, duplicate]):
        errors = check_notification_category_keys_are_unique(None)

    assert [error.id for error in errors] == ["freedom_ls_comms.E001"]


def test_unique_category_keys_produce_no_error() -> None:
    errors = check_notification_category_keys_are_unique(None)

    assert errors == []


def test_a_delivery_backend_path_that_cannot_be_imported_produces_an_error() -> None:
    with override_settings(NOTIFICATION_DELIVERY_BACKENDS=["nowhere.Missing"]):
        errors = check_notification_delivery_backends_import(None)

    assert [error.id for error in errors] == ["freedom_ls_comms.E002"]


def test_no_delivery_backends_configured_produces_no_error() -> None:
    errors = check_notification_delivery_backends_import(None)

    assert errors == []


def test_a_messaging_policy_path_that_cannot_be_imported_produces_an_error() -> None:
    with override_settings(MESSAGING_POLICY="nowhere.Missing"):
        errors = check_messaging_policy_imports(None)

    assert [error.id for error in errors] == ["freedom_ls_comms.E003"]


def test_a_messaging_policy_that_is_not_a_policy_class_produces_an_error() -> None:
    with override_settings(MESSAGING_POLICY="freedom_ls.comms.config.CommsConfig"):
        errors = check_messaging_policy_imports(None)

    assert [error.id for error in errors] == ["freedom_ls_comms.E003"]


def test_the_default_messaging_policy_produces_no_import_error() -> None:
    assert check_messaging_policy_imports(None) == []


def test_a_messaging_policy_in_an_uninstalled_fls_app_produces_an_error() -> None:
    with override_settings(MESSAGING_POLICY="freedom_ls.not_installed.policy.Policy"):
        errors = check_messaging_policy_app_installed(None)

    assert [error.id for error in errors] == ["freedom_ls_comms.E004"]


def test_the_default_messaging_policy_app_is_installed() -> None:
    assert check_messaging_policy_app_installed(None) == []
