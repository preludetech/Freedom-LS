"""Tests for `freedom_ls.accounts.registration_forms`."""

from __future__ import annotations

import pytest

from django.core.exceptions import ImproperlyConfigured

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


def test_load_raises_for_bad_dotted_path():
    with pytest.raises(ImproperlyConfigured, match="Could not import"):
        load_registration_form_classes(["this.module.does.not.exist.AtAll"])


def test_load_raises_for_non_form_class():
    with pytest.raises(ImproperlyConfigured, match=r"not a forms\.Form subclass"):
        load_registration_form_classes([f"{_PATH}.NotAFormClass"])


def test_load_raises_for_form_with_forbidden_field():
    with pytest.raises(ImproperlyConfigured, match="user_id"):
        load_registration_form_classes([f"{_PATH}.ForbiddenFieldForm"])


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


@pytest.mark.django_db
def test_get_incomplete_forms_raises_when_applies_to_returns_none(mock_site_context):
    user = UserFactory()
    with pytest.raises(TypeError, match="applies_to must return True or False"):
        get_incomplete_forms(user, [f"{_PATH}.AppliesToReturnsNoneForm"])


@pytest.mark.django_db
def test_get_incomplete_forms_raises_when_is_complete_returns_none(mock_site_context):
    user = UserFactory()
    with pytest.raises(TypeError, match="is_complete must return True or False"):
        get_incomplete_forms(user, [f"{_PATH}.IsCompleteReturnsNoneForm"])
