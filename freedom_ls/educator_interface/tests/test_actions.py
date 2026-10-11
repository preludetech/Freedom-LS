"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import json
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.actions import cohort_not_empty_sentence
from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.organisations.utils import get_default_organisation


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


# edit a learner's name


def _site_admin_client(site: Site, logged_in_client) -> Client:
    admin = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), admin, "site_admin", site)
    return cast(Client, logged_in_client(admin))


def _edit_name_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/edit_name"
    )


def _named_learner(organisation: Organisation) -> Learner:
    return cast(
        Learner,
        LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name="Ada", last_name="Lovelace"),
        ),
    )


@pytest.mark.django_db
def test_a_site_admins_learner_header_offers_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _edit_name_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_an_organisation_admins_learner_header_offers_no_edit_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    user = UserFactory(staff=True)
    assign_role(UserFactory(superuser=True), user, "organisation_admin", organisation)
    client = logged_in_client(user)

    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))

    document = lxml.html.fromstring(response.content.decode())
    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert _edit_name_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_edit_name_post_changes_the_users_first_name(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    learner.user.refresh_from_db()
    assert learner.user.first_name == "Grace"


@pytest.mark.django_db
def test_edit_name_post_sends_the_new_display_name_as_the_page_title(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, trigger["instanceTitleChanged"]["title"]) == (
        204,
        "Grace Hopper",
    )


@pytest.mark.django_db
def test_edit_name_post_fires_the_learner_changed_event_for_the_learner(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner = _named_learner(organisation)
    client = _site_admin_client(mock_site_context, logged_in_client)

    response = _post(
        client,
        _edit_name_url(organisation, learner),
        {"first_name": "Grace", "last_name": "Hopper"},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


# deactivate and reactivate a learner


def _learner_state_url(
    organisation: Organisation, learner: Learner, action: str
) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/{action}"
    )


def _header_triggers(
    client: Client, organisation: Organisation, learner: Learner
) -> set[str | None]:
    response = client.get(_interface_url(organisation.slug, f"learners/{learner.pk}"))
    document = lxml.html.fromstring(response.content.decode())
    return {button.get("hx-get") for button in document.cssselect("button[hx-get]")}


@pytest.mark.django_db
def test_an_active_learners_header_offers_deactivate_not_reactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (True, False)


@pytest.mark.django_db
def test_a_removed_learners_header_offers_reactivate_not_deactivate(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert (
        _learner_state_url(organisation, learner, "deactivate") in triggers,
        _learner_state_url(organisation, learner, "reactivate") in triggers,
    ) == (False, True)


@pytest.mark.django_db
def test_deactivate_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = LearnerFactory(organisation=default, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(default, learner, "deactivate")
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_deactivate_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = LearnerFactory(organisation=organisation, is_active=True)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_reactivate_fragment_says_access_returns_through_existing_cohorts_and_registrations(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    text = _get_fragment(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert "existing cohorts and registrations" in text


@pytest.mark.django_db
def test_deactivate_post_answers_204_with_a_location_to_the_learner_page(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    location = json.loads(response["HX-Location"])
    assert (response.status_code, location["path"]) == (
        204,
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )


@pytest.mark.django_db
def test_deactivate_post_sets_the_learner_inactive(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    _post(staff_client, _learner_state_url(organisation, learner, "deactivate"))

    learner.refresh_from_db()
    assert learner.is_active is False


@pytest.mark.django_db
def test_reactivate_post_sets_the_learner_active(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    _post(staff_client, _learner_state_url(organisation, learner, "reactivate"))

    learner.refresh_from_db()
    assert learner.is_active is True


@pytest.mark.django_db
def test_deactivating_a_removed_learner_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "deactivate")
    )

    learner.refresh_from_db()
    assert (response.status_code, learner.is_active) == (422, False)


@pytest.mark.django_db
def test_reactivating_an_active_learner_answers_422(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation, is_active=True)

    response = _post(
        staff_client, _learner_state_url(organisation, learner, "reactivate")
    )

    assert response.status_code == 422


# remove from a cohort


def _remove_url_from_learner(
    organisation: Organisation, learner: Learner, cohort: Cohort | None = None
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts"
        "/__actions/remove_from_cohort",
    )
    return f"{url}?cohort={cohort.pk}" if cohort is not None else url


def _remove_url_from_cohort(
    organisation: Organisation, cohort: Cohort, learner: Learner | None = None
) -> str:
    url = _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/remove_from_cohort"
    )
    return f"{url}?learner={learner.pk}" if learner is not None else url


def _membership(organisation: Organisation, **cohort_fields: object):
    cohort = cast(Cohort, CohortFactory(organisation=organisation, **cohort_fields))
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    return learner, cohort


def _remove_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "remove_from_cohort" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learner_page_renders_with_the_remove_action_registered(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, _ = _membership(organisation)

    response = staff_client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_remove_fragment_from_the_learner_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "They lose access to: Algebra." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_remove_fragment_says_the_learner_keeps_every_course_through_another_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client, _remove_url_from_learner(organisation, learner, cohort)
    )

    assert "keep access to every course through another registration" in text


@pytest.mark.django_db
def test_remove_post_from_the_learner_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_remove_post_sends_both_ids_with_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    ids = {"ids": [str(learner.pk), str(cohort.pk)]}
    assert (trigger[LEARNER_CHANGED], trigger[COHORT_CHANGED]) == (ids, ids)
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_remove_fragment_from_the_cohort_page_names_the_courses_lost(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client, _remove_url_from_cohort(organisation, cohort, learner)
    )

    assert "They lose access to: Algebra." in text


@pytest.mark.django_db
def test_remove_post_from_the_cohort_page_deletes_the_membership(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)

    response = _post(
        staff_client,
        _remove_url_from_cohort(organisation, cohort),
        {"learner": str(learner.pk)},
    )

    assert response.status_code == 204
    assert not CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_a_stale_remove_naming_an_inactive_cohort_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, is_active=False)

    response = _post(
        staff_client,
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert "is inactive" in response.content.decode()
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_a_cohort_admins_learner_page_offers_remove_on_the_granted_cohort_only(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    triggers = _remove_triggers(
        logged_in_client(educator),
        _interface_url(organisation.slug, f"learners/{learner.pk}"),
    )

    assert {t.split("?cohort=")[1] for t in triggers} == {str(granted.pk)}


@pytest.mark.django_db
def test_a_forged_remove_on_an_unassigned_cohort_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    other = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=other, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", granted)
    assign_role(grantor, educator, "cohort_viewer", other)

    response = _post(
        logged_in_client(educator),
        _remove_url_from_learner(organisation, learner),
        {"cohort": str(other.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=other).exists()


# add to a cohort


def _add_to_cohort_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
    )


def _add_learners_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(
        organisation, cohort, "/__tabs/learners/__actions/add_existing_learners"
    )


def _offered_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value")
        for option in document.cssselect("option[value]")
        if option.get("value")
    }


def _cohort_admin_on(organisation: Organisation, *cohorts: Cohort):
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    for cohort in cohorts:
        assign_role(grantor, educator, "cohort_admin", cohort)
    return educator


@pytest.mark.django_db
def test_add_to_cohort_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, member_of = _membership(organisation)
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    inactive = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    offered = _offered_options(staff_client, _add_to_cohort_url(organisation, learner))

    assert offered == {str(open_cohort.pk)}
    assert str(member_of.pk) not in offered
    assert str(inactive.pk) not in offered


@pytest.mark.django_db
def test_add_to_cohort_post_adds_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=cohort).exists()


@pytest.mark.django_db
def test_add_to_cohort_post_sends_the_learner_and_cohort_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_add_to_cohort_post_naming_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(cohort.pk)},
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_a_cohort_admins_add_to_cohort_offers_only_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    spare = cast(Cohort, CohortFactory(organisation=organisation))
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted, spare)

    offered = _offered_options(
        logged_in_client(educator), _add_to_cohort_url(organisation, learner)
    )

    assert offered == {str(spare.pk)}
    assert str(unassigned.pk) not in offered


@pytest.mark.django_db
def test_a_forged_add_to_an_unassigned_cohort_answers_403_and_adds_nothing(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, granted = _membership(organisation)
    unassigned = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, granted)

    response = _post(
        logged_in_client(educator),
        _add_to_cohort_url(organisation, learner),
        {"cohort": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert not CohortMembership.objects.filter(
        learner=learner, cohort=unassigned
    ).exists()


def _learner_tab_triggers(client: Client, cohort: Cohort) -> list[str]:
    url = _cohort_url(cohort.organisation, cohort, "/__tabs/learners")
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "add_existing_learners" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_a_cohort_admin_without_add_learner_sees_the_learner_picker_on_the_cohort_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_an_organisation_admin_with_add_learner_sees_no_learner_picker(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "organisation_admin", organisation)

    triggers = _learner_tab_triggers(logged_in_client(educator), cohort)

    assert triggers == []


@pytest.mark.django_db
def test_the_learner_picker_offers_learners_outside_the_cohort(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    member = cast(Learner, LearnerFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=member)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation), learner=outsider
    )
    assign_role(
        LearnerFactory(user__superuser=True).user,
        educator,
        "organisation_admin",
        organisation,
    )

    offered = _offered_options(
        logged_in_client(educator), _add_learners_url(organisation, cohort)
    )

    assert str(member.pk) not in offered
    assert str(outsider.pk) in offered


@pytest.mark.django_db
def test_the_learner_picker_post_adds_each_learner(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 204
    assert set(
        CohortMembership.objects.filter(cohort=cohort).values_list(
            "learner_id", flat=True
        )
    ) == {first.pk, second.pk}


@pytest.mark.django_db
def test_the_learner_picker_post_sends_every_learner_id_and_the_cohort_id(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    first = cast(Learner, LearnerFactory(organisation=organisation))
    second = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(first.pk), str(second.pk)]},
        HTTP_HX_REQUEST="true",
    )

    trigger = json.loads(response["HX-Trigger"])
    assert set(trigger[LEARNER_CHANGED]["ids"]) == {str(first.pk), str(second.pk)}
    assert trigger[COHORT_CHANGED] == {"ids": [str(cohort.pk)]}


@pytest.mark.django_db
def test_a_stale_learner_picker_post_on_an_inactive_cohort_answers_422(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))
    learner = cast(Learner, LearnerFactory(organisation=organisation))

    response = staff_client.post(
        _add_learners_url(organisation, cohort),
        {"learners": [str(learner.pk)]},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert not CohortMembership.objects.filter(cohort=cohort).exists()
