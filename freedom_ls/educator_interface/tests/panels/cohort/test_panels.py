"""The cohort details, completion, name, staff and status panels."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import lxml.html
import pytest

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.sites.models import Site
from django.test import Client
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.content_engine.factories import (
    CourseFactory,
)
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _cohort_page,
    _get_document,
    _interface_url,
    _shared_and_own_course_world,
    organisation_admin_viewer,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


@pytest.mark.django_db
def test_settings_offers_deactivate_on_an_active_cohort(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate" in triggers
    )
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/reactivate"
        not in triggers
    )


@pytest.mark.django_db
def test_settings_offers_reactivate_on_an_inactive_cohort(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, is_active=False)
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in document.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/reactivate" in triggers
    )
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate"
        not in triggers
    )


def _add_cohort_progress(
    registration: CohortCourseRegistration, learner: Learner, completed: bool
) -> None:
    CourseProgressFactory(
        learner=learner,
        course=registration.course,
        learner_registration=None,
        cohort_registration=registration,
        completed_time=timezone.now() if completed else None,
    )


def _completion_card(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (card,) = document.cssselect("section[data-panel='completion']")
    return card


@pytest.fixture
def completion_scenario() -> tuple[Cohort, CohortCourseRegistration, Learner]:
    """A cohort registered for one course, with two members holding one course
    progress record each; the returned learner's record is the completed one."""
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    registration = cast(
        CohortCourseRegistration,
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title="Algebra")
        ),
    )
    done = _add_member(cohort)
    _add_cohort_progress(registration, done, completed=True)
    _add_cohort_progress(registration, _add_member(cohort), completed=False)
    return cohort, registration, done


@pytest.mark.django_db
def test_course_completion_reads_one_of_two_completed(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
) -> None:
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    text = " ".join(card.text_content().split())
    assert "Algebra" in text
    assert "1 of 2 completed" in text


@pytest.mark.django_db
def test_the_course_completion_list_shows_no_list_markers(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
) -> None:
    """The theme bullets and indents bare lists, so the card's rows had both."""
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    (course_list,) = card.cssselect("ul")
    assert "list-none" in course_list.get("class").split()


@pytest.mark.django_db
def test_course_completion_progress_bar_is_at_fifty(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
) -> None:
    cohort, _, _ = completion_scenario

    card = _completion_card(_cohort_page(staff_client, cohort))

    (bar,) = card.cssselect("progress")
    assert bar.get("value") == "50"


@pytest.mark.django_db
def test_course_completion_falls_when_the_completed_member_leaves(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
) -> None:
    cohort, _, done = completion_scenario
    CohortMembership.objects.get(cohort=cohort, learner=done).delete()

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "0 of 1 completed" in " ".join(card.text_content().split())


@pytest.mark.django_db
def test_an_inactive_cohort_still_shows_completion_for_active_registrations(
    staff_client: Client,
    completion_scenario: tuple[Cohort, CohortCourseRegistration, Learner],
) -> None:
    cohort, _, _ = completion_scenario
    cohort.is_active = False
    cohort.save()

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "1 of 2 completed" in " ".join(card.text_content().split())


@pytest.mark.django_db
def test_course_completion_leaves_out_an_inactive_registration(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Retired"), is_active=False
    )

    card = _completion_card(_cohort_page(staff_client, cohort))

    assert "Retired" not in card.text_content()
    assert "No courses registered." in card.text_content()


def _settings_url(organisation: Organisation, cohort: Cohort) -> str:
    return _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings")


def _staff_section(document: lxml.html.HtmlElement) -> lxml.html.HtmlElement:
    (section,) = document.cssselect("section[data-panel='staff']")
    return section


@pytest.mark.django_db
def test_the_settings_tab_names_each_staff_member_and_their_role(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="Ada", user__last_name="Lovelace", organisation=organisation
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    text = " ".join(_staff_section(document).text_content().split())
    assert "Ada Lovelace" in text
    assert "Cohort Admin" in text or "Cohort admin" in text
    assert not document.cssselect("section[data-panel='educators']")


@pytest.mark.django_db
def test_the_settings_tab_staff_names_are_small_semibold_beside_a_small_avatar(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    """A staff member is the small person row. The name used to render at the
    base size and regular weight beside a medium avatar."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="Ada", user__last_name="Lovelace", organisation=organisation
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    (name,) = [
        n
        for n in _staff_section(document).cssselect("span.truncate")
        if n.text_content().strip() == "Ada Lovelace"
    ]
    classes = " ".join(
        " ".join(
            a.get("class", "")
            for a in [name, *name.iterancestors("span", "div")]
            if a.getparent() is not None and a.tag != "li"
        ).split()
    )
    assert "text-sm" in classes
    assert "font-semibold" in classes
    assert _staff_section(document).cssselect("span.size-6")
    assert not _staff_section(document).cssselect("span.size-8")


@pytest.mark.django_db
def test_the_settings_tab_shows_a_nameless_staff_members_email_as_stored(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(
        user__first_name="",
        user__last_name="",
        user__email="Mixed.Case@Example.com",
        organisation=organisation,
    ).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    assert "Mixed.Case@Example.com" in _staff_section(document).text_content()


@pytest.mark.django_db
def test_the_settings_tab_lists_a_person_added_from_the_cohort_page(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    ada = UserFactory(first_name="Ada", last_name="Lovelace", email="ada@example.com")
    client = logged_in_client(admin)

    client.post(
        _settings_url(organisation, cohort)
        + "/__panels/staff/__actions/add_staff_member",
        {
            "step": "submit",
            "email": "ada@example.com",
            "role": "cohort_viewer",
            "cohorts": [str(cohort.pk)],
            "confirmed": "1",
        },
        HTTP_HX_REQUEST="true",
    )

    document = _get_document(client, _settings_url(organisation, cohort))
    assert ada.display_name in _staff_section(document).text_content()


@pytest.mark.django_db
def test_the_settings_tab_offers_add_staff_member_beside_its_staff_heading(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(staff_client, _settings_url(organisation, cohort))

    section = _staff_section(document)
    assert "No staff assigned to this cohort." in section.text_content()
    (trigger,) = section.cssselect("button[hx-get]")
    assert trigger.get("hx-get") == (
        _settings_url(organisation, cohort)
        + "/__panels/staff/__actions/add_staff_member"
    )
    assert "btn-sm" in trigger.get("class").split()
    footer_urls = {
        b.get("hx-get")
        for b in document.cssselect("section[data-panel] footer button")
        if b.get("hx-get")
    }
    assert not any(url.endswith("/__actions/add_staff_member") for url in footer_urls)


def _staff_on(
    organisation: Organisation, cohort: Cohort, role: str = "cohort_admin"
) -> User:
    holder = cast(
        User, LearnerFactory(user__staff=True, organisation=organisation).user
    )
    assign_role(LearnerFactory(user__superuser=True).user, holder, role, cohort)
    return holder


def _staff_triggers(section: lxml.html.HtmlElement) -> list[str]:
    return [button.get("hx-get") for button in section.cssselect("button[hx-get]")]


@pytest.mark.django_db
def test_a_cohort_admin_sees_the_staff_section_alone_on_the_settings_tab(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    me = _staff_on(organisation, cohort)
    _staff_on(organisation, cohort, "cohort_viewer")

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    page = _settings_url(organisation, cohort)
    assert f"{page}/__panels/staff/__actions/add_staff_member" in _staff_triggers(
        _staff_section(document)
    )
    assert not document.cssselect("form[hx-post$='/__actions/edit']")
    assert "Deactivating stops" not in document.text_content()
    assert not document.cssselect("section[data-panel='status']")
    assert not document.cssselect("section[data-panel='name']")


@pytest.mark.django_db
def test_each_cohort_role_row_offers_change_role_and_remove_from_cohort_the_viewers_own_included(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    me = _staff_on(organisation, cohort)
    colleague = _staff_on(organisation, cohort, "cohort_viewer")

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    actions = f"{_settings_url(organisation, cohort)}/__panels/staff/__actions"
    assert set(_staff_triggers(_staff_section(document))) == {
        f"{actions}/change_role?user={colleague.pk}&role=cohort_viewer",
        f"{actions}/remove_staff_from_cohort?user={colleague.pk}&role=cohort_viewer",
        f"{actions}/change_role?user={me.pk}&role=cohort_admin",
        f"{actions}/remove_staff_from_cohort?user={me.pk}&role=cohort_admin",
        f"{actions}/add_staff_member",
    }


@pytest.mark.django_db
def test_an_organisation_role_row_shows_only_its_role_to_a_viewer_who_can_open_staff(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    other = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        other,
        "organisation_admin",
        organisation,
    )

    document = _get_document(
        logged_in_client(admin), _settings_url(organisation, cohort)
    )

    section = _staff_section(document)
    (row,) = [
        li for li in section.cssselect("li") if other.display_name in li.text_content()
    ]
    assert "Organisation admin" in row.text_content()
    assert "whole organisation" not in row.text_content().lower()
    assert "Change it in Staff" not in row.text_content()
    assert not row.cssselect("button")
    assert not row.cssselect("a[href$='/staff']")


@pytest.mark.django_db
def test_an_organisation_role_row_shows_only_its_role_to_a_cohort_admin(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(
        LearnerFactory(user__superuser=True).user,
        admin,
        "organisation_admin",
        organisation,
    )
    me = _staff_on(organisation, cohort)

    document = _get_document(logged_in_client(me), _settings_url(organisation, cohort))

    section = _staff_section(document)
    assert "Organisation admin" in section.text_content()
    assert "Set for the whole organisation." not in section.text_content()
    assert not section.cssselect("a[href$='/staff']")


@pytest.mark.django_db
def test_the_cohort_settings_panel_refreshes_on_member_changes(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(staff_client, _settings_url(organisation, cohort))

    (card,) = document.cssselect("section[data-panel='staff']")
    assert "staffChanged from:body" in card.get("hx-trigger")


@pytest.mark.django_db
def test_cohort_course_completion_names_the_owner_of_a_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
) -> None:
    """The cohort's course completion rows named a shared course by its bare
    title."""
    organisation, own, shared = _shared_and_own_course_world()
    cohort = CohortFactory(organisation=organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=shared)
    CohortCourseRegistrationFactory(cohort=cohort, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(
        client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/overview"),
    )

    text = " ".join(document.text_content().split())
    assert text.count("Shared by Northwind Logistics") == 1
    assert "Shared by Northwind Logistics · 0 of 0 completed" in text
