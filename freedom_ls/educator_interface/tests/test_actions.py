"""The educator interface's panel actions, driven through the interface URLs."""

from __future__ import annotations

import json
from typing import cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.config import config
from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.educator_interface.actions import cohort_not_empty_sentence
from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
    LEARNER_CHANGED,
    REGISTRATION_CHANGED,
)
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
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_progress.factories import CourseProgressFactory
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


# add learners


def _add_learners_list_url(organisation: Organisation) -> str:
    return _interface_url(organisation.slug, "learners/__actions/add_learners")


def _add_learners_tab_url(organisation: Organisation, cohort: Cohort) -> str:
    return _cohort_url(organisation, cohort, "/__tabs/learners/__actions/add_learners")


def _organisation_admin_on(organisation: Organisation):
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "organisation_admin", organisation)
    return educator


def _list_triggers(client: Client, organisation: Organisation) -> list[str]:
    document = lxml.html.fromstring(
        client.get(_interface_url(organisation.slug, "learners")).content.decode()
    )
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "__actions/add_learners" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_the_learners_list_offers_add_learners_to_an_organisation_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    educator = _organisation_admin_on(organisation)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert len(triggers) == 1


@pytest.mark.django_db
def test_the_learners_list_offers_no_add_learners_to_a_cohort_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    educator = _cohort_admin_on(organisation, cohort)

    triggers = _list_triggers(logged_in_client(educator), organisation)

    assert triggers == []


@pytest.mark.django_db
def test_add_learners_offers_only_active_cohorts_the_user_may_add_to(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    open_cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortFactory(organisation=organisation, is_active=False)
    CohortFactory(organisation=OrganisationFactory())

    offered = _offered_options(staff_client, _add_learners_list_url(organisation))

    assert offered == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_add_learners_renders_a_preset_cohort_as_a_hidden_input(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = staff_client.get(
        _add_learners_list_url(organisation),
        {"cohort": str(cohort.pk)},
        HTTP_HX_REQUEST="true",
    )

    document = lxml.html.fromstring(response.content.decode())
    hidden = document.cssselect("input[type=hidden][name=cohort]")
    assert [field.get("value") for field in hidden] == [str(cohort.pk)]


@pytest.mark.django_db
def test_add_learners_post_without_entries_answers_422(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client, _add_learners_list_url(organisation), {"entries": ""}
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_add_learners_post_answers_200_with_the_results_and_creates_the_learners(
    staff_client: Client,
):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com, Nia, Okoye\nbad-address"},
    )

    assert response.status_code == 200
    assert "Account created and setup email sent" in response.content.decode()
    assert "Not a valid email address" in response.content.decode()
    assert Learner.objects.filter(
        organisation=organisation, user__email="new@example.com"
    ).exists()


@pytest.mark.django_db
def test_add_learners_post_sends_the_learner_changed_trigger(staff_client: Client):
    organisation = OrganisationFactory()

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com"},
    )

    assert LEARNER_CHANGED in json.loads(response["HX-Trigger"])


@pytest.mark.django_db
def test_add_learners_post_with_a_cohort_sends_the_cohort_changed_trigger_and_adds_them(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_list_url(organisation),
        {"entries": "new@example.com", "cohort": str(cohort.pk)},
    )

    assert COHORT_CHANGED in json.loads(response["HX-Trigger"])
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_add_learners_post_on_a_cohort_tab_adds_to_that_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"entries": "new@example.com"},
    )

    assert response.status_code == 200
    assert cohort.cohortmembership_set.count() == 1


@pytest.mark.django_db
def test_the_cohort_tab_title_names_the_cohort(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, name="Wave One"))

    fragment = _get_fragment(staff_client, _add_learners_tab_url(organisation, cohort))

    assert "Add learners to Wave One" in fragment


@pytest.mark.django_db
def test_an_organisation_admins_cohort_tab_offers_add_learners_not_the_picker(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    client = logged_in_client(_organisation_admin_on(organisation))
    url = _cohort_url(organisation, cohort, "/__tabs/learners")

    document = lxml.html.fromstring(client.get(url).content.decode())

    hx_gets = [
        button.get("hx-get") or "" for button in document.cssselect("button[hx-get]")
    ]
    assert [g.rsplit("/", 1)[-1] for g in hx_gets if "__actions/add" in g] == [
        "add_learners"
    ]


@pytest.mark.django_db
def test_an_inactive_cohorts_tab_offers_no_add_learners(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    html = staff_client.get(
        _cohort_url(organisation, cohort, "/__tabs/learners")
    ).content.decode()

    assert "__actions/add_learners" not in html


@pytest.mark.django_db
def test_a_stale_add_learners_post_on_an_inactive_cohort_answers_422_and_adds_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation, is_active=False))

    response = _post(
        staff_client,
        _add_learners_tab_url(organisation, cohort),
        {"entries": "new@example.com"},
    )

    assert response.status_code == 422
    assert not Learner.objects.filter(user__email="new@example.com").exists()


# resend the account setup email


@pytest.fixture
def _clear_resend_guard():
    cache.clear()
    yield
    cache.clear()


def _resend_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/resend_setup_email"
    )


def _pending_learner(organisation: Organisation) -> Learner:
    user = UserFactory(email="pending@example.com", last_login=None)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return cast(Learner, LearnerFactory(organisation=organisation, user=user))


@pytest.mark.django_db
def test_a_pending_learners_header_offers_resend_setup_email(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) in triggers


@pytest.mark.django_db
def test_a_learner_who_has_set_up_their_account_is_offered_no_resend(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    triggers = _header_triggers(staff_client, organisation, learner)

    assert _resend_url(organisation, learner) not in triggers


@pytest.mark.django_db
def test_resend_fragment_names_the_address(staff_client: Client):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    text = _get_fragment(staff_client, _resend_url(organisation, learner))

    assert "pending@example.com" in text


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_sends_one_message_and_answers_204(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (204, 1)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_post_fires_learner_changed_and_closes_the_modal(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    events = json.loads(response["HX-Trigger"])
    assert (events[LEARNER_CHANGED], "closeModal" in events) == (
        {"ids": [str(learner.pk)]},
        True,
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_second_resend_answers_422_with_the_minutes_to_wait(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    with django_capture_on_commit_callbacks(execute=True):
        _post(staff_client, _resend_url(organisation, learner))

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    minutes = config.SETUP_EMAIL_RESEND_SECONDS // 60
    assert (response.status_code, len(mail.outbox)) == (422, 1)
    assert f"{minutes} minutes" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_resend_for_a_learner_who_has_set_up_answers_422_and_sends_nothing(
    staff_client: Client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(staff_client, _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (422, 0)


@pytest.mark.django_db
@pytest.mark.usefixtures("_clear_resend_guard")
def test_a_cohort_admins_forged_resend_answers_403_and_sends_nothing(
    mock_site_context: Site, logged_in_client, django_capture_on_commit_callbacks
):
    organisation = OrganisationFactory()
    learner = _pending_learner(organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    with django_capture_on_commit_callbacks(execute=True):
        response = _post(logged_in_client(educator), _resend_url(organisation, learner))

    assert (response.status_code, len(mail.outbox)) == (403, 0)


# move between cohorts


def _move_url_from_learner(
    organisation: Organisation,
    learner: Learner,
    source: Cohort | None = None,
    destination: Cohort | None = None,
) -> str:
    url = _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/cohorts/__actions/move",
    )
    params = []
    if source is not None:
        params.append(f"cohort={source.pk}")
    if destination is not None:
        params.append(f"destination={destination.pk}")
    return f"{url}?{'&'.join(params)}" if params else url


def _move_url_from_cohort(
    organisation: Organisation, source: Cohort, learner: Learner
) -> str:
    url = _cohort_url(organisation, source, "/__tabs/learners/__actions/move")
    return f"{url}?learner={learner.pk}"


def _move_options(client: Client, url: str) -> set[str]:
    response = client.get(url, HTTP_HX_REQUEST="true")
    document = lxml.html.fromstring(response.content.decode())
    return {
        option.get("value") or ""
        for option in document.cssselect("select[name='destination'] option")
        if option.get("value")
    }


@pytest.mark.django_db
def test_move_fragment_offers_only_active_cohorts_the_learner_is_not_in(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    open_cohort = CohortFactory(organisation=organisation)
    CohortFactory(organisation=organisation, is_active=False)
    already_in = CohortFactory(organisation=organisation)
    CohortMembershipFactory(cohort=already_in, learner=learner)

    options = _move_options(
        staff_client, _move_url_from_learner(organisation, learner, source)
    )

    assert options == {str(open_cohort.pk)}


@pytest.mark.django_db
def test_move_fragment_names_courses_lost_gained_and_where_progress_continues(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    shared = CourseFactory(title="Algebra")
    lost = CourseFactory(title="Botany")
    gained = CourseFactory(title="Chemistry")
    source_registration = CohortCourseRegistrationFactory(cohort=source, course=shared)
    CohortCourseRegistrationFactory(cohort=source, course=lost)
    CohortCourseRegistrationFactory(cohort=destination, course=shared)
    CohortCourseRegistrationFactory(cohort=destination, course=gained)
    CourseProgressFactory(
        learner=learner,
        course=shared,
        learner_registration=None,
        cohort_registration=source_registration,
        progress_percentage=40,
    )

    text = _get_fragment(
        staff_client,
        _move_url_from_learner(organisation, learner, source, destination),
    )

    assert "They lose access to: Botany." in text
    assert "They gain access to: Chemistry." in text
    assert "Algebra: continues at 40%" in text


@pytest.mark.django_db
def test_move_post_moves_the_membership_and_answers_204_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert set(trigger[COHORT_CHANGED]["ids"]) == {
        str(learner.pk),
        str(source.pk),
        str(destination.pk),
    }
    assert str(learner.pk) in trigger[LEARNER_CHANGED]["ids"]
    assert list(CohortMembership.objects.filter(learner=learner)) == [
        CohortMembership.objects.get(learner=learner, cohort=destination)
    ]


@pytest.mark.django_db
def test_move_post_from_the_cohort_page_moves_the_membership(staff_client: Client):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_cohort(organisation, source, learner),
        {"learner": str(learner.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204
    assert CohortMembership.objects.filter(learner=learner, cohort=destination).exists()


@pytest.mark.django_db
def test_move_post_to_a_cohort_outside_the_users_grants_answers_403(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    unassigned = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(unassigned.pk)},
    )

    assert response.status_code == 403
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_a_cohort_admin_can_move_between_two_assigned_cohorts(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", source)
    assign_role(grantor, educator, "cohort_admin", destination)

    response = _post(
        logged_in_client(educator),
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 204


@pytest.mark.django_db
def test_move_post_naming_an_inactive_source_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation, is_active=False)
    destination = CohortFactory(organisation=organisation)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


@pytest.mark.django_db
def test_move_post_naming_an_inactive_destination_answers_422_and_changes_nothing(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner, source = _membership(organisation)
    destination = CohortFactory(organisation=organisation, is_active=False)

    response = _post(
        staff_client,
        _move_url_from_learner(organisation, learner),
        {"cohort": str(source.pk), "destination": str(destination.pk)},
    )

    assert response.status_code == 422
    assert CohortMembership.objects.filter(learner=learner, cohort=source).exists()


# register and unregister a learner individually


def _learner_register_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug, f"learners/{learner.pk}/__actions/register_for_course"
    )


def _learner_unregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/unregister_from_course",
    )


@pytest.mark.django_db
def test_register_fragment_offers_the_registerable_courses(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    open_course = CourseFactory()
    coming_soon = CourseFactory(visibility=CourseVisibility.COMING_SOON)
    held = LearnerCourseRegistrationFactory(learner=learner, is_active=True).course

    offered = _offered_options(
        staff_client, _learner_register_url(organisation, learner)
    )

    assert offered == {str(open_course.pk)}
    assert str(coming_soon.pk) not in offered
    assert str(held.pk) not in offered


@pytest.mark.django_db
def test_register_post_creates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course, is_active=True
    ).exists()
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}
    assert "closeModal" in trigger


@pytest.mark.django_db
def test_register_post_naming_a_coming_soon_course_answers_422_with_no_row(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory(visibility=CourseVisibility.COMING_SOON)

    response = _post(
        staff_client,
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 422
    assert not LearnerCourseRegistration.objects.filter(learner=learner).exists()


@pytest.mark.django_db
def test_unregister_fragment_names_the_cohort_keeping_access(staff_client: Client):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation, name="Year 10")
    course = CourseFactory(title="Algebra")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    registration = LearnerCourseRegistrationFactory(learner=learner, course=course)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They keep access through Year 10." in text
    assert "Progress is kept." in text


@pytest.mark.django_db
def test_unregister_fragment_says_the_learner_loses_access_without_a_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "They lose access to Algebra." in text


@pytest.mark.django_db
def test_unregister_fragment_names_self_registration_only_on_the_default_organisation(
    staff_client: Client, mock_site_context: Site
):
    default = get_default_organisation(mock_site_context)
    learner = cast(Learner, LearnerFactory(organisation=default))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(default, learner) + f"?registration={registration.pk}",
    )

    assert "self-register" in text


@pytest.mark.django_db
def test_unregister_fragment_omits_self_registration_on_another_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory(is_default=False)
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    text = _get_fragment(
        staff_client,
        _learner_unregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert "self-register" not in text


@pytest.mark.django_db
def test_unregister_post_deactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner)

    response = _post(
        staff_client,
        _learner_unregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, False)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_a_cohort_admin_can_register_a_learner_in_an_assigned_cohort(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, learner),
        {"course": str(course.pk)},
    )

    assert response.status_code == 204
    assert LearnerCourseRegistration.objects.filter(
        learner=learner, course=course
    ).exists()


@pytest.mark.django_db
def test_a_cohort_admins_forged_register_on_a_learner_outside_their_cohorts_is_refused(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    _, cohort = _membership(organisation)
    outsider = cast(Learner, LearnerFactory(organisation=organisation))
    course = CourseFactory()
    educator = _cohort_admin_on(organisation, cohort)

    response = _post(
        logged_in_client(educator),
        _learner_register_url(organisation, outsider),
        {"course": str(course.pk)},
    )

    assert response.status_code == 404
    assert not LearnerCourseRegistration.objects.filter(learner=outsider).exists()


# re-register a learner individually


def _learner_reregister_url(organisation: Organisation, learner: Learner) -> str:
    return _interface_url(
        organisation.slug,
        f"learners/{learner.pk}/__tabs/overview/__panels/registrations"
        "/__actions/reregister_for_course",
    )


def _reregister_triggers(client: Client, url: str) -> list[str]:
    document = lxml.html.fromstring(client.get(url).content.decode())
    return [
        button.get("hx-get") or ""
        for button in document.cssselect("button[hx-get]")
        if "reregister_for_course" in (button.get("hx-get") or "")
    ]


@pytest.mark.django_db
def test_reregister_is_offered_on_an_inactive_individual_row_only(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    inactive = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, is_active=True)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=False)

    triggers = _reregister_triggers(
        staff_client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )

    assert [t.split("?registration=")[1] for t in triggers] == [str(inactive.pk)]


@pytest.mark.django_db
def test_reregister_fragment_names_the_learner_and_the_course(staff_client: Client):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra"), is_active=False
    )

    text = _get_fragment(
        staff_client,
        _learner_reregister_url(organisation, learner)
        + f"?registration={registration.pk}",
    )

    assert f"Register {learner.user.display_name} for Algebra again?" in text


@pytest.mark.django_db
def test_reregister_post_reactivates_the_registration_with_both_events(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    trigger = json.loads(response["HX-Trigger"])
    assert (response.status_code, registration.is_active) == (204, True)
    assert trigger[REGISTRATION_CHANGED] == {"ids": [str(learner.pk)]}
    assert trigger[LEARNER_CHANGED] == {"ids": [str(learner.pk)]}


@pytest.mark.django_db
def test_reregister_post_naming_an_active_registration_answers_404(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = cast(Learner, LearnerFactory(organisation=organisation))
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=True)

    response = _post(
        staff_client,
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_cohort_viewers_forged_reregister_answers_403(
    mock_site_context: Site, logged_in_client
):
    organisation = OrganisationFactory()
    learner, cohort = _membership(organisation)
    registration = LearnerCourseRegistrationFactory(learner=learner, is_active=False)
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    response = _post(
        logged_in_client(viewer),
        _learner_reregister_url(organisation, learner),
        {"registration": str(registration.pk)},
    )

    registration.refresh_from_db()
    assert (response.status_code, registration.is_active) == (403, False)
