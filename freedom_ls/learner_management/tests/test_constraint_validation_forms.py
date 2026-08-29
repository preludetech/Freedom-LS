"""The admin forms guarding site-scoped constraints.

SiteAwareModelAdmin excludes ``site`` from every admin form, and
UniqueConstraint.validate() abandons a constraint whose field sits in that
exclusion set. Each admin form here un-excludes ``site`` via
ConstraintValidationFormMixin, so a duplicate row surfaces as the model's own
uniqueness error on the form instead of an IntegrityError from the database.

The mixin's own set arithmetic is tested in
``site_aware_models/tests/test_forms.py``; these are the wiring checks that
each form actually takes it.
"""

from __future__ import annotations

import pytest

from django.core.exceptions import NON_FIELD_ERRORS

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
from freedom_ls.organisations.factories import OrganisationFactory

pytestmark = pytest.mark.django_db


def _duplicate_cohort():
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    return {"organisation": organisation.pk, "name": "Year 10 Science"}


def _duplicate_learner():
    learner = LearnerFactory()
    return {
        "user": learner.user_id,
        "organisation": learner.organisation_id,
        "is_active": True,
    }


def _duplicate_learner_course_registration():
    registration = LearnerCourseRegistrationFactory()
    return {
        "learner": registration.learner_id,
        "course": registration.course_id,
        "is_active": True,
    }


def _duplicate_cohort_course_registration():
    registration = CohortCourseRegistrationFactory()
    return {
        "cohort": registration.cohort_id,
        "course": registration.course_id,
        "is_active": True,
    }


# The expected message names the constraint's fields in the constraint's own
# order, which is what distinguishes one constraint's error from another's.
DUPLICATE_CASES = [
    (
        CohortAdminForm,
        _duplicate_cohort,
        "Cohort with this Site, Organisation and Name already exists.",
    ),
    (
        LearnerAdminForm,
        _duplicate_learner,
        "Learner with this Site, User and Organisation already exists.",
    ),
    (
        LearnerCourseRegistrationAdminForm,
        _duplicate_learner_course_registration,
        "Learner course registration with this Site, Learner and Course "
        "already exists.",
    ),
    (
        CohortCourseRegistrationAdminForm,
        _duplicate_cohort_course_registration,
        "Cohort course registration with this Site, Course and Cohort already exists.",
    ),
]


@pytest.mark.parametrize(
    ("form_class", "build_duplicate", "expected_message"),
    DUPLICATE_CASES,
    ids=[form_class.__name__ for form_class, _, _ in DUPLICATE_CASES],
)
def test_admin_form_reports_a_duplicate_as_a_form_error(
    mock_site_context, form_class, build_duplicate, expected_message
):
    form = form_class(data=build_duplicate())

    assert form.is_valid() is False
    assert form.errors[NON_FIELD_ERRORS] == [expected_message]


def test_learner_admin_form_accepts_a_genuinely_new_learner(mock_site_context):
    """The negative control: an over-eager mixin would reject this too."""
    organisation = OrganisationFactory()
    other_organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)
    user = LearnerFactory(organisation=other_organisation).user

    form = LearnerAdminForm(
        data={"user": user.pk, "organisation": organisation.pk, "is_active": True}
    )

    assert form.is_valid(), form.errors
