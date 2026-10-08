"""Tests for the hr_attributes models."""

from __future__ import annotations

import pytest

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

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
from freedom_ls.hr_attributes.models import LearnerHRAttributes

LIST_FACTORIES = [JobTitleFactory, DepartmentFactory, LocationFactory]
HOLDING_FIELD_BY_FACTORY = {
    JobTitleFactory: "job_title",
    DepartmentFactory: "department",
    LocationFactory: "location",
}


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
@pytest.mark.parametrize(
    ("first_name", "second_name"),
    [("Finance", "FINANCE"), ("Finance", " Finance "), ("Finance", "  fINANCE")],
)
def test_names_differing_by_case_or_whitespace_are_one_entry_per_organisation(
    mock_site_context, factory_class, first_name, second_name
):
    # Arrange
    organisation = OrganisationFactory()
    factory_class(organisation=organisation, name=first_name)

    # Act / Assert
    with pytest.raises(IntegrityError), transaction.atomic():
        factory_class(organisation=organisation, name=second_name)


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_two_organisations_may_share_an_entry_name(mock_site_context, factory_class):
    # Arrange
    first = factory_class(name="Finance")

    # Act
    second = factory_class(name="Finance")

    # Assert
    assert first.organisation_id != second.organisation_id
    assert second.pk is not None


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_inactive_entry_prints_with_inactive_suffix(mock_site_context, factory_class):
    # Arrange
    entry = factory_class(name="Finance", is_active=False)

    # Act / Assert
    assert str(entry) == "Finance (inactive)"


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_active_entry_prints_as_its_name(mock_site_context, factory_class):
    # Arrange
    entry = factory_class(name="Finance", is_active=True)

    # Act / Assert
    assert str(entry) == "Finance"


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_deleting_a_held_entry_raises_protected_error(mock_site_context, factory_class):
    # Arrange
    attributes = LearnerHRAttributesFactory()
    entry = getattr(attributes, HOLDING_FIELD_BY_FACTORY[factory_class])

    # Act / Assert
    with pytest.raises(ProtectedError):
        entry.delete()


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_deleting_an_unused_entry_succeeds(mock_site_context, factory_class):
    # Arrange
    entry = factory_class()

    # Act
    entry.delete()

    # Assert
    assert not factory_class._meta.model.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_deleting_the_learners_user_removes_their_attributes(mock_site_context):
    # Arrange
    attributes = LearnerHRAttributesFactory(
        job_title=None, department=None, location=None
    )

    # Act
    attributes.learner.user.delete()

    # Assert
    assert not LearnerHRAttributes.objects.filter(pk=attributes.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_full_clean_strips_surrounding_whitespace_from_name(
    mock_site_context, factory_class
):
    # Arrange
    entry = factory_class.build(organisation=OrganisationFactory(), name=" Finance ")

    # Act
    entry.full_clean()

    # Assert
    assert entry.name == "Finance"


@pytest.mark.django_db
@pytest.mark.parametrize("factory_class", LIST_FACTORIES)
def test_full_clean_keeps_the_case_of_name(mock_site_context, factory_class):
    # Arrange
    entry = factory_class.build(organisation=OrganisationFactory(), name="IT")

    # Act
    entry.full_clean()

    # Assert
    assert entry.name == "IT"
