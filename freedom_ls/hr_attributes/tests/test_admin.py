"""Tests for the hr_attributes list admins."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.hr_attributes"):
    pytest.skip("hr_attributes not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
)

CASES = [
    pytest.param(JobTitleFactory, "jobtitle", "job_title", id="job_title"),
    pytest.param(DepartmentFactory, "department", "department", id="department"),
    pytest.param(LocationFactory, "location", "location", id="location"),
]


def _url(model_name: str, view: str, *args: object) -> str:
    return reverse(f"admin:freedom_ls_hr_attributes_{model_name}_{view}", args=args)


def _changelist_names(response) -> set[str]:
    return {entry.name for entry in response.context["cl"].result_list}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_changelist_loads(staff_client, factory_class, model_name, field):
    # Arrange
    entry = factory_class()

    # Act
    response = staff_client.get(_url(model_name, "changelist"))

    # Assert
    assert response.status_code == 200
    assert _changelist_names(response) == {entry.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_organisation_filter_narrows_to_that_organisation(
    staff_client, factory_class, model_name, field
):
    # Arrange
    wanted = factory_class()
    factory_class()

    # Act
    response = staff_client.get(
        _url(model_name, "changelist"),
        {"organisation__id__exact": wanted.organisation.pk},
    )

    # Assert
    assert _changelist_names(response) == {wanted.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_inactive_filter_narrows_to_inactive_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    inactive = factory_class(is_active=False)
    factory_class(is_active=True)

    # Act
    response = staff_client.get(
        _url(model_name, "changelist"), {"is_active__exact": "0"}
    )

    # Assert
    assert _changelist_names(response) == {inactive.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_deactivate_action_deactivates_the_selected_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    first, second = factory_class(), factory_class()

    # Act
    response = staff_client.post(
        _url(model_name, "changelist"),
        {"action": "deactivate_selected", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    # Assert
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.is_active, second.is_active) == (False, False)
    assert "2 entries deactivated." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_activate_action_activates_the_selected_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    first = factory_class(is_active=False)
    second = factory_class(is_active=False)

    # Act
    response = staff_client.post(
        _url(model_name, "changelist"),
        {"action": "activate_selected", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    # Assert
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.is_active, second.is_active) == (True, True)
    assert "2 entries activated." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_delete_of_a_held_entry_is_refused_and_names_the_attributes_row(
    staff_client, factory_class, model_name, field
):
    # Arrange
    entry = factory_class()
    LearnerHRAttributesFactory(**{field: entry})

    # Act
    response = staff_client.post(_url(model_name, "delete", entry.pk), {"post": "yes"})

    # Assert
    assert response.status_code == 200
    assert type(entry).objects.filter(pk=entry.pk).exists()
    assert "HR attributes for" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_delete_of_an_unused_entry_deletes_it(
    staff_client, factory_class, model_name, field
):
    # Arrange
    entry = factory_class()

    # Act
    staff_client.post(_url(model_name, "delete", entry.pk), {"post": "yes"})

    # Assert
    assert not type(entry).objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_add_form_with_a_case_variant_duplicate_creates_no_row(
    staff_client, factory_class, model_name, field
):
    # Arrange
    existing = factory_class(name="Finance")
    organisation = existing.organisation
    OrganisationFactory()

    # Act
    response = staff_client.post(
        _url(model_name, "add"),
        {"organisation": organisation.pk, "name": "FINANCE", "is_active": "on"},
    )

    # Assert
    assert response.status_code == 200
    assert type(existing).objects.count() == 1
    assert "An entry with this name already exists" in response.content.decode()
