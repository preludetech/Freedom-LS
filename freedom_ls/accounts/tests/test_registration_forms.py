"""Tests for `freedom_ls.accounts.registration_forms`."""

from __future__ import annotations

import logging

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.registration_forms import (
    get_incomplete_forms,
    load_registration_form_classes,
)
from freedom_ls.accounts.tests._registration_form_fixtures import (
    GoodForm,
)

_PATH = "freedom_ls.accounts.tests._registration_form_fixtures"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_load_returns_empty_for_no_paths():
    assert load_registration_form_classes([]) == []


def test_load_skips_bad_dotted_path(caplog):
    with caplog.at_level(logging.WARNING):
        result = load_registration_form_classes(["this.module.does.not.exist.AtAll"])
    assert result == []
    assert any("Could not import" in r.message for r in caplog.records)


def test_load_skips_non_form_class(caplog):
    with caplog.at_level(logging.WARNING):
        result = load_registration_form_classes([f"{_PATH}.NotAFormClass"])
    assert result == []
    assert any("not a forms.Form subclass" in r.message for r in caplog.records)


def test_load_skips_form_with_forbidden_field(caplog):
    with caplog.at_level(logging.WARNING):
        result = load_registration_form_classes([f"{_PATH}.ForbiddenFieldForm"])
    assert result == []
    assert any("forbidden user-identifying field" in r.message for r in caplog.records)


def test_load_returns_compliant_class():
    result = load_registration_form_classes([f"{_PATH}.GoodForm"])
    assert result == [GoodForm]


@pytest.mark.django_db
def test_get_incomplete_forms_short_circuits_for_superuser(mock_site_context):
    user = UserFactory(superuser=True)
    result = get_incomplete_forms(user, [f"{_PATH}.GoodForm"])
    assert result == []


@pytest.mark.django_db
def test_get_incomplete_forms_filters_out_complete(mock_site_context):
    user = UserFactory()
    result = get_incomplete_forms(user, [f"{_PATH}.GoodForm", f"{_PATH}.CompleteForm"])
    assert result == [GoodForm]


@pytest.mark.django_db
def test_get_incomplete_forms_filters_out_does_not_apply(mock_site_context):
    user = UserFactory()
    result = get_incomplete_forms(
        user, [f"{_PATH}.GoodForm", f"{_PATH}.DoesNotApplyForm"]
    )
    assert result == [GoodForm]


@pytest.mark.django_db
def test_get_incomplete_forms_propagates_applies_to_error(mock_site_context):
    user = UserFactory()
    with pytest.raises(RuntimeError, match="boom in applies_to"):
        get_incomplete_forms(user, [f"{_PATH}.RaisesInAppliesToForm"])


@pytest.mark.django_db
def test_get_incomplete_forms_propagates_is_complete_error(mock_site_context):
    user = UserFactory()
    with pytest.raises(RuntimeError, match="boom in is_complete"):
        get_incomplete_forms(user, [f"{_PATH}.RaisesInIsCompleteForm"])
