"""Tests for the hr_attributes list entry forms."""

from __future__ import annotations

import pytest

from django.forms import modelform_factory

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.hr_attributes"):
    pytest.skip("hr_attributes not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LocationFactory,
)
from freedom_ls.hr_attributes.forms import ListEntryForm


def _form_class(factory_class):
    return modelform_factory(
        factory_class._meta.model,
        form=ListEntryForm,
        fields=["organisation", "name", "is_active"],
    )


CASES = [
    (JobTitleFactory, _form_class(JobTitleFactory)),
    (DepartmentFactory, _form_class(DepartmentFactory)),
    (LocationFactory, _form_class(LocationFactory)),
]
DUPLICATE_MESSAGE = "An entry with this name already exists in this organisation."


def _data(organisation, name):
    return {"organisation": organisation.pk, "name": name, "is_active": "on"}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "form_class"), CASES)
@pytest.mark.parametrize("duplicate_name", ["FINANCE", " Finance ", "  fINANCE"])
def test_name_matching_an_existing_entry_errors_on_name(
    mock_site_context, factory_class, form_class, duplicate_name
):
    # Arrange
    existing = factory_class(name="Finance")
    form = form_class(data=_data(existing.organisation, duplicate_name))

    # Act
    valid = form.is_valid()

    # Assert
    assert valid is False
    assert form.errors == {"name": [DUPLICATE_MESSAGE]}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "form_class"), CASES)
def test_editing_an_entry_without_changing_its_name_is_valid(
    mock_site_context, factory_class, form_class
):
    # Arrange
    entry = factory_class(name="Finance")
    form = form_class(data=_data(entry.organisation, "Finance"), instance=entry)

    # Act
    valid = form.is_valid()

    # Assert
    assert valid is True


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "form_class"), CASES)
def test_same_name_in_another_organisation_is_valid(
    mock_site_context, factory_class, form_class
):
    # Arrange
    factory_class(name="Finance")
    other_organisation = OrganisationFactory()
    form = form_class(data=_data(other_organisation, "Finance"))

    # Act
    valid = form.is_valid()

    # Assert
    assert valid is True
