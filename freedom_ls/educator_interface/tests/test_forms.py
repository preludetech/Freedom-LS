"""Tests for the educator interface's forms."""

from __future__ import annotations

import pytest

from django.http import QueryDict

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.forms import (
    AddLearnerForm,
    AddStaffMemberForm,
    CohortCourseRegistrationForm,
    CohortSetForm,
    LearnerPickerForm,
    choice_error,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import LearnerEntry
from freedom_ls.learner_management.models import Cohort, Learner
from freedom_ls.learner_management.queries import registerable_courses_for


@pytest.mark.django_db
def test_registration_form_offers_only_the_registerable_courses(mock_site_context):
    cohort = CohortFactory()
    CourseFactory(visibility=CourseVisibility.COMING_SOON)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)
    open_course = CourseFactory()

    form = CohortCourseRegistrationForm(cohort=cohort)

    assert list(form.fields["course"].queryset) == [open_course]
    assert list(form.fields["course"].queryset) == list(
        registerable_courses_for(cohort)
    )


@pytest.mark.django_db
def test_registration_form_rejects_a_coming_soon_course(mock_site_context):
    cohort = CohortFactory()
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    form = CohortCourseRegistrationForm({"course": str(course.pk)}, cohort=cohort)

    assert form.is_valid() is False
    assert "course" in form.errors


@pytest.mark.django_db
def test_registration_form_accepts_a_published_course(mock_site_context):
    cohort = CohortFactory()
    course = CourseFactory()

    form = CohortCourseRegistrationForm({"course": str(course.pk)}, cohort=cohort)

    assert form.is_valid() is True


def test_choice_error_names_the_lowercased_choice() -> None:
    assert choice_error("Course") == {
        "invalid_choice": "Choose a course from the list.",
        "invalid_pk_value": "Choose a course from the list.",
    }


@pytest.mark.django_db
def test_learner_picker_form_keeps_a_malformed_id_out_of_its_error() -> None:
    data = QueryDict(mutable=True)
    data.setlist("learners", ["not-a-uuid"])
    form = LearnerPickerForm(data, queryset=Learner.objects.all())

    assert form.is_valid() is False
    assert form.errors["learners"] == ["Choose a learner from the list."]


def _add_form(data: dict[str, str]) -> AddLearnerForm:
    return AddLearnerForm(data, cohorts=Cohort.objects.none())


@pytest.mark.django_db
def test_add_learner_form_builds_the_entry_from_email_and_names():
    form = _add_form(
        {"email": " ada@example.com ", "first_name": "Ada", "last_name": "Lovelace"}
    )

    assert form.is_valid()
    assert form.entry() == LearnerEntry("ada@example.com", "Ada", "Lovelace")


@pytest.mark.django_db
def test_add_learner_form_needs_only_the_email():
    form = _add_form({"email": "bob@example.com"})

    assert form.is_valid()
    assert form.entry() == LearnerEntry("bob@example.com")


@pytest.mark.django_db
def test_add_learner_form_refuses_an_empty_email():
    form = _add_form({"email": " "})

    assert form.is_valid() is False
    assert "email" in form.errors


@pytest.mark.django_db
def test_add_learner_form_refuses_an_invalid_address():
    form = _add_form({"email": "not-an-email"})

    assert form.is_valid() is False
    assert "email" in form.errors


@pytest.mark.django_db
def test_learner_picker_labels_each_learner_by_display_name(mock_site_context):
    named = LearnerFactory(
        user__first_name="Ada",
        user__last_name="Lovelace",
        user__email="ada@example.com",
    )
    unnamed = LearnerFactory(
        user__first_name="", user__last_name="", user__email="pick@example.com"
    )

    form = LearnerPickerForm(
        queryset=Learner.objects.filter(pk__in=[named.pk, unnamed.pk])
    )

    labels = {label for _, label in form.fields["learners"].choices}
    assert labels == {"Ada Lovelace", "pick@example.com"}


def _staff_member_form(
    data: dict[str, str | list[str]],
    preset: Cohort | None = None,
    allow_no_role: bool = False,
) -> AddStaffMemberForm:
    return AddStaffMemberForm(
        _query_dict(data),
        roles=[
            ("organisation_admin", "Organisation admin"),
            ("cohort_admin", "Cohort admin"),
        ],
        cohorts=Cohort.objects.all(),
        preset=preset,
        allow_no_role=allow_no_role,
    )


def _query_dict(data: dict[str, str | list[str]]) -> QueryDict:
    query = QueryDict(mutable=True)
    for name, value in data.items():
        query.setlist(name, value if isinstance(value, list) else [value])
    return query


@pytest.mark.django_db
def test_add_member_form_accepts_an_empty_role_with_no_cohorts_when_allowed(
    mock_site_context,
):
    form = _staff_member_form(
        {"email": "a@example.com", "role": ""}, allow_no_role=True
    )

    assert form.is_valid()
    assert form.cleaned_data["role"] == ""
    assert not form.cleaned_data["cohorts"]


@pytest.mark.django_db
def test_add_member_form_rejects_an_empty_role_when_not_allowed(mock_site_context):
    form = _staff_member_form({"email": "a@example.com", "role": ""})

    assert not form.is_valid()
    assert "role" in form.errors


@pytest.mark.django_db
def test_add_member_form_requires_a_cohort_for_a_cohort_role(mock_site_context):
    form = _staff_member_form({"email": "a@example.com", "role": "cohort_admin"})

    assert not form.is_valid()
    assert form.errors["cohorts"] == ["Choose at least one cohort."]


@pytest.mark.django_db
def test_add_member_form_needs_no_cohort_for_organisation_admin(mock_site_context):
    cohort = CohortFactory()
    form = _staff_member_form(
        {
            "email": "a@example.com",
            "role": "organisation_admin",
            "cohorts": [str(cohort.pk)],
        }
    )

    assert form.is_valid()
    assert list(form.cleaned_data["cohorts"]) == []


@pytest.mark.django_db
def test_add_member_form_accepts_a_cohort_role_with_a_cohort(mock_site_context):
    cohort = CohortFactory()
    form = _staff_member_form(
        {"email": "a@example.com", "role": "cohort_admin", "cohorts": [str(cohort.pk)]}
    )

    assert form.is_valid()
    assert list(form.cleaned_data["cohorts"]) == [cohort]


@pytest.mark.django_db
def test_add_member_form_hides_and_fixes_a_preset_cohort(mock_site_context):
    cohort = CohortFactory()

    form = _staff_member_form({}, preset=cohort)

    field = form.fields["cohorts"]
    assert (field.widget.is_hidden, field.initial) == (True, [cohort.pk])


def test_an_empty_cohort_selection_is_valid():
    form = CohortSetForm(QueryDict(""))

    assert form.is_valid()
    assert list(form.cleaned_data["cohorts"]) == []
