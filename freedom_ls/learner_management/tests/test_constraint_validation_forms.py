"""Regression tests for the admin forms guarding site-scoped constraints.

SiteAwareModelAdmin excludes ``site`` from every admin form, and
UniqueConstraint.validate() abandons a constraint whose field sits in that
exclusion set. Each admin form under test un-excludes ``site`` via
ConstraintValidationFormMixin, so a duplicate row surfaces as a form error
instead of an IntegrityError from the database.
"""

from __future__ import annotations

import pytest

from django.core.exceptions import NON_FIELD_ERRORS
from django.db import IntegrityError

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.forms import (
    CohortAdminForm,
    CohortCourseRegistrationAdminForm,
    LearnerAdminForm,
    LearnerCourseRegistrationAdminForm,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
def test_cohort_name_may_repeat_across_organisations_on_one_site(mock_site_context):
    CohortFactory(organisation=OrganisationFactory(), name="Year 10 Science")

    Cohort.objects.create(organisation=OrganisationFactory(), name="Year 10 Science")

    assert Cohort.objects.filter(name="Year 10 Science").count() == 2


@pytest.mark.django_db
def test_cohort_name_cannot_repeat_within_one_organisation(mock_site_context):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")

    with pytest.raises(IntegrityError):
        Cohort.objects.create(organisation=organisation, name="Year 10 Science")


@pytest.mark.django_db
def test_cohort_admin_form_rejects_duplicate_name_with_a_form_error(mock_site_context):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")

    form = CohortAdminForm(
        data={"organisation": organisation.pk, "name": "Year 10 Science"}
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors


@pytest.mark.django_db
def test_learner_admin_form_rejects_duplicate_user_organisation_pair(
    mock_site_context,
):
    learner = LearnerFactory()

    form = LearnerAdminForm(
        data={
            "user": learner.user_id,
            "organisation": learner.organisation_id,
            "is_active": True,
        }
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors


@pytest.mark.django_db
def test_learner_course_registration_admin_form_rejects_duplicate(mock_site_context):
    registration = LearnerCourseRegistrationFactory()

    form = LearnerCourseRegistrationAdminForm(
        data={
            "learner": registration.learner_id,
            "course": registration.course_id,
            "is_active": True,
        }
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors


@pytest.mark.django_db
def test_cohort_course_registration_admin_form_rejects_duplicate(mock_site_context):
    registration = CohortCourseRegistrationFactory()

    form = CohortCourseRegistrationAdminForm(
        data={
            "cohort": registration.cohort_id,
            "course": registration.course_id,
            "is_active": True,
        }
    )

    assert form.is_valid() is False
    assert NON_FIELD_ERRORS in form.errors


@pytest.mark.django_db
def test_learner_admin_form_accepts_a_genuinely_new_learner(mock_site_context):
    organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)
    user = LearnerFactory(organisation=other_organisation).user

    form = LearnerAdminForm(
        data={"user": user.pk, "organisation": organisation.pk, "is_active": True}
    )

    assert form.is_valid(), form.errors
