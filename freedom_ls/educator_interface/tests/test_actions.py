"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import json
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.actions import cohort_not_empty_sentence
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortCourseRegistration
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


def _interface_url(organisation_slug: str, path_string: str) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={"organisation_slug": organisation_slug, "path_string": path_string},
    )


def _cohort_url(organisation: Organisation, cohort: Cohort, suffix: str = "") -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}{suffix}")


def _cohort_with_courses(
    organisation: Organisation, course_count: int, **cohort_fields: object
) -> Cohort:
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    for _ in range(course_count):
        CohortCourseRegistrationFactory(cohort=cohort)
    return cohort


def _get_fragment(client: Client, url: str) -> str:
    response = client.get(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    return " ".join(
        lxml.html.fromstring(response.content.decode()).text_content().split()
    )


def _post(client: Client, url: str, data: dict[str, str] | None = None):
    return client.post(url, data or {}, HTTP_HX_REQUEST="true")


# rename clash


@pytest.mark.django_db
def test_renaming_a_cohort_onto_a_sibling_name_answers_422_and_keeps_the_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation, name="Year 10 Science")
    cohort = CohortFactory(organisation=organisation, name="Year 11 Science")

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "Year 10 Science"},
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert "Another cohort already has this name." in response.content.decode()
    assert cohort.name == "Year 11 Science"


# deactivate


@pytest.mark.django_db
def test_deactivate_fragment_names_how_many_courses_stop_giving_access(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 2, name="Evening group")

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "Deactivate Evening group" in text
    assert "stop giving access to its 2 courses" in text


@pytest.mark.django_db
def test_deactivate_fragment_says_why_a_non_empty_cohort_cannot_be_deleted(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert (
        "Evening group can't be deleted while it has 1 learner and 1 course "
        "registration, counting removed learners and inactive registrations." in text
    )


@pytest.mark.django_db
def test_deactivate_fragment_of_an_empty_cohort_does_not_mention_deleting(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert "can't be deleted" not in text


@pytest.mark.django_db
def test_deactivate_post_sets_the_cohort_inactive(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    _post(staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate"))

    cohort.refresh_from_db()
    assert cohort.is_active is False


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_cohort_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort
    )


@pytest.mark.django_db
def test_stale_deactivate_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/deactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 422
    assert cohort.is_active is False


# reactivate


@pytest.mark.django_db
def test_reactivate_fragment_names_how_many_courses_give_access_again(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 3, name="Old group", is_active=False)

    text = _get_fragment(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert "Reactivate Old group" in text
    assert "give access to its 3 courses again" in text


@pytest.mark.django_db
def test_reactivate_post_sets_the_cohort_active(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1, is_active=False)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    cohort.refresh_from_db()
    assert response.status_code == 204
    assert cohort.is_active is True


@pytest.mark.django_db
def test_stale_reactivate_on_an_active_cohort_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 1)

    response = _post(
        staff_client, _cohort_url(organisation, cohort, "/__actions/reactivate")
    )

    assert response.status_code == 422
    assert "is already active" in response.content.decode()


@pytest.mark.django_db
def test_cohort_not_empty_sentence_counts_removed_learners_and_inactive_registrations(
    mock_site_context,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    removed = LearnerFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(cohort=cohort, learner=removed)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    sentence = cohort_not_empty_sentence(cohort)

    assert sentence == (
        "Evening group can't be deleted while it has 2 learners and 1 course "
        "registration, counting removed learners and inactive registrations."
    )


@pytest.mark.django_db
def test_not_empty_sentence_pluralises_course_registrations(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 2, name="Evening group")

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 2 course registrations, counting" in sentence


@pytest.mark.django_db
def test_not_empty_sentence_never_names_a_zero_count(mock_site_context: Site) -> None:
    """ "0 learners" reads as a reason, and is not one."""
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )

    sentence = cohort_not_empty_sentence(cohort)

    assert "while it has 1 learner, counting" in sentence
    assert "0 course" not in sentence


@pytest.mark.django_db
def test_not_empty_sentence_is_empty_for_an_empty_cohort(
    mock_site_context: Site,
) -> None:
    cohort = _cohort_with_courses(OrganisationFactory(), 0)

    assert cohort_not_empty_sentence(cohort) == ""


# inactive cohorts are read-only


@pytest.mark.django_db
def test_an_inactive_cohorts_page_renders_no_edit_trigger(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, is_active=False)

    response = staff_client.get(_cohort_url(organisation, cohort))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _cohort_url(organisation, cohort, "/__actions/edit") not in triggers


@pytest.mark.django_db
def test_editing_an_inactive_cohort_answers_422_with_the_inactive_fragment(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    response = _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()


@pytest.mark.django_db
def test_editing_an_inactive_cohort_leaves_its_name_unchanged(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)

    _post(
        staff_client,
        _cohort_url(organisation, cohort, "/__actions/edit"),
        {"name": "New name"},
    )

    cohort.refresh_from_db()
    assert cohort.name == "Old group"


# register


def _register_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/courses/__actions/register")


@pytest.mark.django_db
def test_register_fragment_title_names_the_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Evening group")

    text = _get_fragment(staff_client, _register_url(organisation, cohort))

    assert "Register Evening group for a course" in text


@pytest.mark.django_db
def test_register_post_answers_204_with_a_location_to_the_courses_tab(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_register_post_creates_the_registration(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0)
    course = CourseFactory()

    _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert cohort.course_registrations.filter(course=course, is_active=True).exists()


@pytest.mark.django_db
def test_register_post_on_an_inactive_cohort_answers_422_and_creates_no_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = _cohort_with_courses(organisation, 0, name="Old group", is_active=False)
    course = CourseFactory()

    response = _post(
        staff_client,
        _register_url(organisation, cohort),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()
    assert not cohort.course_registrations.exists()


# unregister


def _unregister_post_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/courses/__actions/unregister")


def _unregister_url(
    organisation: Organisation,
    cohort: Cohort,
    registration: CohortCourseRegistration | str,
) -> str:
    pk = registration if isinstance(registration, str) else registration.pk
    return f"{_unregister_post_url(organisation, cohort)}?registration={pk}"


def _member(organisation: Organisation, cohort: Cohort, first_name: str = "Ada"):
    learner = LearnerFactory(
        organisation=organisation, user__first_name=first_name, user__last_name="Lee"
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner


def _registered_cohort(
    organisation: Organisation, course_title: str = "Algebra", **cohort_fields: object
):
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    registration = CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title=course_title)
    )
    return cohort, registration


@pytest.mark.django_db
def test_unregister_fragment_title_names_the_cohort_and_course(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation, name="Evening group")

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Unregister Evening group from Algebra" in text


@pytest.mark.django_db
def test_unregister_fragment_counts_members_who_lose_access(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort, "Ada")
    _member(organisation, cohort, "Bea")
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "2 learners lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_an_individual_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Cy")
    LearnerCourseRegistrationFactory(
        learner=kept, course=registration.course, is_active=True
    )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "These learners keep access through another registration: Cy Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_a_member_kept_by_another_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    kept = _member(organisation, cohort, "Dee")
    other = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=other, learner=kept)
    CohortCourseRegistrationFactory(cohort=other, course=registration.course)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration: Dee Lee." in text


@pytest.mark.django_db
def test_unregister_fragment_names_the_first_ten_keepers_and_counts_the_rest(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    for index in range(12):
        learner = _member(organisation, cohort, f"Keeper{index:02d}")
        LearnerCourseRegistrationFactory(
            learner=learner, course=registration.course, is_active=True
        )

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "Keeper09 Lee and 2 more." in text
    assert "Keeper10" not in text


@pytest.mark.django_db
def test_unregister_fragment_omits_the_keepers_sentence_when_nobody_keeps_access(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    _member(organisation, cohort)

    text = _get_fragment(
        staff_client, _unregister_url(organisation, cohort, registration)
    )

    assert "keep access through another registration" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_unregister_post_answers_204_with_a_location_to_the_courses_tab(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204
    assert json.loads(response["HX-Location"])["path"] == _cohort_url(
        organisation, cohort, "/__tabs/courses"
    )


@pytest.mark.django_db
def test_a_cohort_admin_can_unregister_on_their_own_cohort(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = _post(
        logged_in_client(educator),
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_answers_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    response = staff_client.get(
        _unregister_url(organisation, cohort, foreign), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_registration_from_another_cohort_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)
    _, foreign = _registered_cohort(organisation, "Geometry")

    _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(foreign.pk)},
    )

    foreign.refresh_from_db()
    assert foreign.is_active is True


@pytest.mark.django_db
def test_unregister_with_an_inactive_registration_answers_404(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    registration = CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    response = staff_client.get(
        _unregister_url(organisation, cohort, registration), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unregister_with_a_malformed_registration_answers_404(staff_client: Client):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _unregister_url(organisation, cohort, "not-a-uuid"), HTTP_HX_REQUEST="true"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_courses_tab_footer_offers_register_but_no_unregister_button(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, _ = _registered_cohort(organisation)

    response = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/courses"), HTTP_HX_REQUEST="true"
    )

    footer_urls = [
        button.get("hx-get")
        for button in lxml.html.fromstring(response.content.decode()).cssselect(
            "button[hx-get]"
        )
    ]
    register_url = _register_url(organisation, cohort)
    assert register_url in footer_urls
    assert not [url for url in footer_urls if url.endswith("/__actions/unregister")]


@pytest.mark.django_db
def test_unregister_post_on_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort, registration = _registered_cohort(
        organisation, name="Old group", is_active=False
    )

    response = _post(
        staff_client,
        _unregister_post_url(organisation, cohort),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert response.status_code == 422
    assert "Old group is inactive" in response.content.decode()
    assert registration.is_active is True
