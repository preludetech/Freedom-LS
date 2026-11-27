"""The cohort Learners, Courses and History tabs: educator_interface/panels/cohort/data_table_panels.py."""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import cast

import lxml.html
import pytest
from panel_framework.tables import DataTable

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.sites.models import Site
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _audit_log_rows,
    _audit_log_url,
    _card_summary,
    _cohort_history_tab,
    _cohort_history_url,
    _cohort_page,
    _export_audit_csv,
    _export_csv,
    _get_document,
    _history_rows,
    _interface_url,
    _region_text,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import add_to_cohort
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.learner_management.utils import register_cohort_for_course
from freedom_ls.learner_progress.tests.helpers import course_progress_record
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.tests.site_context import drop_ambient_request


@pytest.mark.django_db
def test_the_learners_tab_url_renders_the_cohorts_learners(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Lovelace"
    )
    CohortMembershipFactory(cohort=cohort, learner=learner)

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"),
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]
    assert active.text_content().split()[0] == "Learners"
    (region,) = document.cssselect("[data-tab-set]")
    assert "Lovelace" in region.text_content()
    assert "Course completion" not in region.text_content()


# A cohort page holds two tables, its course registrations on the Courses
# tab and its learners on the Learners tab. Each paginates through its own
# table key, so a learners page in the address bar leaves the course
# registrations on their own page.


def _cohort_url(cohort: Cohort) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": cohort.organisation.slug,
            "path_string": f"cohorts/{cohort.pk}",
        },
    )


@pytest.mark.django_db
def test_learners_page_param_leaves_course_registrations_on_page_one(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Big Cohort")
    for i in range(DataTable.get_page_size() + 1):
        learner = LearnerFactory(
            user=UserFactory(first_name=f"Learner{i:02d}", last_name="Test"),
            organisation=organisation,
        )
        CohortMembershipFactory(cohort=cohort, learner=learner)
    for i in range(2):
        CohortCourseRegistrationFactory(
            cohort=cohort, course=CourseFactory(title=f"Course {i}")
        )
    client = logged_in_client(UserFactory(superuser=True))

    learners_tab = client.get(
        f"{_cohort_url(cohort)}/__tabs/learners", {"learners-page": "2"}
    )
    courses_tab = client.get(
        f"{_cohort_url(cohort)}/__tabs/courses", {"learners-page": "2"}
    )

    assert learners_tab.status_code == 200
    content = learners_tab.content.decode()
    # The learners table is on its own page 2: the last learner shows, the
    # 1st (on page 1) does not.
    assert f"Learner{DataTable.get_page_size():02d}" in content
    assert "Learner00" not in content
    # The course registrations table is untouched, still on page 1.
    assert courses_tab.status_code == 200
    content = courses_tab.content.decode()
    assert "Course 0" in content
    assert "Course 1" in content


def _register_triggers(document: lxml.html.HtmlElement, cohort: Cohort) -> list[str]:
    url = _interface_url(
        cohort.organisation.slug,
        f"cohorts/{cohort.pk}/__tabs/courses/__actions/register",
    )
    return [
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get") == url
    ]


@pytest.mark.django_db
def test_the_courses_tab_offers_register_to_a_cohort_admin(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    document = _get_document(
        logged_in_client(educator),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (trigger,) = [
        button
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get", "").endswith("/__actions/register")
    ]
    assert " ".join(trigger.text_content().split()) == "Register for a course"
    assert len(_register_triggers(document, cohort)) == 1


@pytest.mark.django_db
def test_the_courses_tab_shows_a_cohort_viewer_no_register_trigger(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    document = _get_document(
        logged_in_client(viewer),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _register_triggers(document, cohort) == []


@pytest.mark.django_db
def test_an_inactive_cohorts_courses_tab_shows_no_register_trigger(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _register_triggers(document, cohort) == []


def _deactivate_triggers(document: lxml.html.HtmlElement, cohort: Cohort) -> list[str]:
    prefix = _interface_url(
        cohort.organisation.slug,
        f"cohorts/{cohort.pk}/__tabs/courses/__actions/deactivate_cohort_registration",
    )
    return [
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if button.get("hx-get").startswith(prefix)
    ]


@pytest.mark.django_db
def test_the_courses_tab_offers_deactivate_only_on_active_registrations(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    active = CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra"), is_active=True
    )
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Geometry"), is_active=False
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    # The table and its small-screen card list each render the trigger.
    (trigger,) = set(_deactivate_triggers(document, cohort))
    assert trigger.endswith(f"?registration={active.pk}")


@pytest.mark.django_db
def test_an_inactive_cohorts_courses_tab_shows_no_deactivate_trigger(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    assert _deactivate_triggers(document, cohort) == []


@pytest.mark.django_db
def test_a_cohort_viewers_courses_tab_renders_no_action_buttons(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    cohort = cast(Cohort, CohortFactory(organisation=OrganisationFactory()))
    CohortCourseRegistrationFactory(cohort=cohort, is_active=True)
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=cohort.organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)

    document = _get_document(
        logged_in_client(viewer),
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    (region,) = document.cssselect("[data-tab-set]")
    assert region.cssselect("button[hx-get]") == []


def _cohort_history_access(
    client: Client, organisation: Organisation, cohort: Cohort
) -> tuple[bool, int]:
    """Whether the cohort page lists a History tab, and the status of the
    tab's own URL."""
    page = client.get(_interface_url(organisation.slug, f"cohorts/{cohort.pk}"))
    hrefs = []
    if page.status_code == 200:
        document = lxml.html.fromstring(page.content.decode())
        (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
        hrefs = [a.get("href").rsplit("/", 1)[-1] for a in nav.cssselect("a")]
    response = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )
    return "history" in hrefs, response.status_code


@pytest.mark.django_db
def test_a_cohort_admin_reads_the_history_of_a_cohort_they_administer(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    colleague = UserFactory()
    assign_role(grantor, colleague, "cohort_viewer", cohort)
    client = logged_in_client(educator)

    shown = _cohort_history_access(client, organisation, cohort)
    history = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    assert shown == (True, 200)
    assert "Role assigned" in history.content.decode()


@pytest.mark.django_db
def test_a_cohort_admin_gets_no_history_on_a_cohort_they_do_not_administer(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    own = cast(Cohort, CohortFactory(organisation=organisation))
    other = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", own)
    assign_role(grantor, educator, "cohort_viewer", other)

    assert _cohort_history_access(logged_in_client(educator), organisation, other) == (
        False,
        404,
    )


@pytest.mark.django_db
def test_an_active_cohorts_learners_tab_offers_remove_for_each_member(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    member = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    triggers = {
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if "remove_from_cohort" in button.get("hx-get")
    }
    assert {t.split("?learner=")[1] for t in triggers} == {str(member.pk)}


@pytest.mark.django_db
def test_a_learner_rows_remove_trigger_uses_the_secondary_variant(
    staff_client: Client,
) -> None:
    """The per-row Remove trigger is secondary; only its dialog's confirm is red."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    buttons = [
        b
        for b in document.cssselect("button[hx-get]")
        if "remove_from_cohort?learner=" in b.get("hx-get")
    ]
    assert buttons
    assert all("btn-secondary" in b.get("class") for b in buttons)
    assert not any("btn-error" in b.get("class") for b in buttons)


@pytest.mark.django_db
def test_a_learner_rows_remove_and_move_triggers_name_the_learner(
    staff_client: Client,
) -> None:
    """Ten rows of bare 'Remove' and 'Move' are indistinguishable to a screen reader."""
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Cohort Alpha")
    learner = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if f"?learner={learner.pk}" in button.get("hx-get")
    }
    assert labels == {
        f"Remove {learner.user.display_name} from Cohort Alpha",
        f"Move {learner.user.display_name} to another cohort",
    }


@pytest.mark.django_db
def test_a_registration_rows_deactivate_trigger_names_the_course(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra"), is_active=True
    )

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/courses"),
    )

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if "deactivate_cohort_registration?registration=" in button.get("hx-get")
    }
    assert labels == {"Deactivate the Algebra registration"}


@pytest.mark.django_db
def test_a_cohorts_learners_tab_exports_its_members_as_a_csv_named_for_the_cohort(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Night class")
    course = CourseFactory(title="Hydrology")
    CohortCourseRegistrationFactory(cohort=cohort, course=course)
    member = CohortMembershipFactory(
        cohort=cohort,
        learner__organisation=organisation,
        learner__user=UserFactory(
            first_name="Ada", last_name="Able", email="ada@example.com"
        ),
    ).learner
    course_progress_record(course, member.user, last_accessed_time=timezone.now())
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation, name="Day class"),
        learner__organisation=organisation,
        learner__user=UserFactory(first_name="Bo", last_name="Baker"),
    )

    header, rows, disposition = _export_csv(
        staff_client, f"cohorts/{cohort.pk}/__tabs/learners", organisation
    )

    assert header == ["Name", "Email", "Status", "Cohorts", "Courses", "Last active"]
    assert [row[:5] for row in rows] == [
        ["Ada Able", "ada@example.com", "Active", "Night class", "Hydrology"]
    ]
    assert rows[0][5] == timezone.localdate().strftime("%Y-%m-%d")
    assert disposition == (
        f'attachment; filename="learners-night-class-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_learners_export_neutralises_a_formula_looking_name_and_leaves_never_active_blank(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    CohortMembershipFactory(
        cohort=CohortFactory(organisation=organisation),
        learner__organisation=organisation,
        learner__user=UserFactory(
            first_name='=HYPERLINK("http://evil","x")',
            last_name="",
            last_active=None,
        ),
    )

    _header, rows, _disposition = _export_csv(staff_client, "learners", organisation)

    (row,) = rows
    assert row[0].startswith("'=HYPERLINK")
    assert row[5] == ""


@pytest.mark.django_db
def test_the_learners_export_stays_scoped_when_the_site_thread_local_is_cleared(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    for name in ("Ada", "Bo"):
        CohortMembershipFactory(
            cohort=CohortFactory(organisation=organisation),
            learner__organisation=organisation,
            learner__user=UserFactory(first_name=name, last_name="Learner"),
        )

    response = staff_client.get(
        _interface_url(organisation.slug, "learners"), {"learners-export": "csv"}
    )
    drop_ambient_request()
    body = b"".join(response.streaming_content).decode("utf-8-sig")

    _header, *rows = list(csv.reader(io.StringIO(body, newline="")))
    assert sorted(row[0] for row in rows) == ["Ada Learner", "Bo Learner"]


@pytest.mark.django_db
def test_the_learners_tab_toolbar_offers_the_csv_export(staff_client: Client) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("learners-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_remove_control(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "remove_from_cohort" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_add_learners_control(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "add_existing_learners" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_an_inactive_cohorts_learners_tab_renders_no_move_control(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)
    _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    assert "__actions/move" not in lxml.html.tostring(document).decode()


@pytest.mark.django_db
def test_an_active_cohorts_learners_tab_offers_move_for_each_member(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    member = _add_member(cohort)

    document = _get_document(
        staff_client,
        _interface_url(
            cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/learners"
        ),
    )

    triggers = {
        button.get("hx-get")
        for button in document.cssselect("button[hx-get]")
        if "__actions/move" in button.get("hx-get")
    }
    assert {t.split("?learner=")[1] for t in triggers} == {str(member.pk)}


@pytest.mark.django_db
def test_the_cohort_history_panel_refreshes_on_member_changes(
    staff_client: Client,
) -> None:
    """Adding a staff member from the Settings tab writes a role.assigned
    entry with the cohort as subject and answers with staffChanged alone."""
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))

    document = _get_document(
        staff_client,
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )

    (card,) = document.cssselect("section[data-panel='history']")
    assert "staffChanged from:body" in card.get("hx-trigger")


@pytest.mark.django_db
def test_an_add_shows_on_the_cohort_history_tab_and_not_on_another_cohort(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    other = CohortFactory(organisation=organisation, name="Beta")
    add_to_cohort(learner, cohort, actor=UserFactory())

    rows = _history_rows(_cohort_history_tab(staff_client, cohort))
    other_page = _cohort_history_tab(staff_client, other)

    assert (
        ["Alpha" in row[2] for row in rows],
        "Alpha" in _region_text(other_page),
    ) == (
        [True],
        False,
    )


@pytest.mark.django_db
def test_the_cohort_history_tab_renders_its_empty_state(staff_client: Client) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())

    response = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


@pytest.mark.django_db
def test_a_cohort_viewer_gets_no_cohort_history_tab_and_a_404_on_its_url(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    viewer = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, viewer, "cohort_viewer", cohort)
    client = logged_in_client(viewer)

    document = _cohort_page(client, cohort)
    response = client.get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    )

    hrefs = [a.get("href").rsplit("/", 1)[-1] for a in document.cssselect("nav a")]
    assert ("history" in hrefs, response.status_code) == (False, 404)


@pytest.mark.django_db
def test_a_cohort_registration_shows_on_the_cohort_history_tab(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    register_cohort_for_course(cohort, CourseFactory(title="Algebra"))

    document = _get_document(
        staff_client,
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history"),
    )

    rows = _history_rows(document)
    assert [row[2] for row in rows] == ["Cohort registered for course Algebra"]


@pytest.mark.django_db
def test_the_cohort_history_tab_names_who_each_row_is_about(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Alpha")
    actor = UserFactory()
    for first_name in ["Ben", "Pat"]:
        learner = LearnerFactory(
            organisation=organisation,
            user=UserFactory(first_name=first_name, last_name="Learner"),
        )
        add_to_cohort(learner, cohort, actor=actor)

    document = _cohort_history_tab(staff_client, cohort)

    headers = [
        th.text_content().strip()
        for th in document.cssselect("[data-tab-set] thead th")
    ]
    rows = _history_rows(document)
    assert (headers, sorted(row[3].split(maxsplit=1)[1] for row in rows)) == (
        ["Details", "When", "Who", "What", "Target"],
        ["Ben Learner", "Pat Learner"],
    )


@pytest.mark.django_db
def test_the_cohort_history_card_names_who_the_row_is_about(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=cohort,
        organisation=cohort.organisation,
        target_label="<b>bold</b>",
    )

    html = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}/__tabs/history")
    ).content.decode()

    assert html.count("&lt;b&gt;bold&lt;/b&gt;") >= 2


@pytest.mark.django_db
def test_the_cohort_history_card_shows_the_label_then_labelled_when_who_and_target(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=cohort,
        organisation=cohort.organisation,
        action="learner.deactivated",
        actor_label="Ada Admin",
        target_label="Alpha",
        reason="Asked to leave",
    )

    document = _cohort_history_tab(staff_client, cohort)

    (card,) = document.cssselect("[data-tab-set] ul > li")
    assert _card_summary(card) == (
        "Learner deactivated",
        ["When", "Who", "Target"],
        ["Ada Admin", "Alpha"],
        True,
    )


def _cohort_entry(cohort: Cohort, **overrides: object) -> AuditLogEntry:
    return cast(
        AuditLogEntry,
        AuditLogEntryFactory(
            target=cohort,
            organisation=cohort.organisation,
            action="cohort.updated",
            **overrides,
        ),
    )


@pytest.mark.django_db
def test_the_cohort_history_export_holds_only_entries_naming_the_cohort(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    other = CohortFactory(organisation=organisation)
    for number in range(30):
        _cohort_entry(cohort, reason=f"reason {number}")
    _cohort_entry(other, reason="not ours")

    _header, rows, _disposition = _export_audit_csv(
        staff_client, _cohort_history_url(cohort)
    )

    assert (len(rows), "not ours" in {row[7] for row in rows}) == (30, False)


@pytest.mark.django_db
def test_the_cohort_history_export_is_named_for_the_cohort(
    staff_client: Client,
) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory(), name="Spring Intake")
    _cohort_entry(cohort)

    _header, _rows, disposition = _export_audit_csv(
        staff_client, _cohort_history_url(cohort)
    )

    assert disposition == (
        f'attachment; filename="history-spring-intake-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
def test_the_cohort_history_export_records_an_entry_for_the_audit_log_only(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Spring Intake")
    _cohort_entry(cohort)

    _export_audit_csv(staff_client, _cohort_history_url(cohort))

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    audit_rows = _audit_log_rows(
        _get_document(staff_client, _audit_log_url(organisation))
    )
    history_rows = _history_rows(_cohort_history_tab(staff_client, cohort))
    assert (
        entry.details,
        len([row for row in audit_rows if "Audit log exported" in row[2]]),
        len(history_rows),
    ) == (
        {
            "scope": "cohort",
            "scope_label": "Spring Intake",
            "count": 1,
            "filters": "",
        },
        1,
        1,
    )


@pytest.mark.django_db
def test_the_cohort_history_toolbar_offers_the_csv_export(staff_client: Client) -> None:
    cohort = CohortFactory(organisation=OrganisationFactory())
    _cohort_entry(cohort)

    document = _cohort_history_tab(staff_client, cohort)

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("history-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_a_cohort_admin_exports_the_history_of_a_cohort_they_administer(
    mock_site_context: Site, logged_in_client: Callable[[AbstractBaseUser], Client]
) -> None:
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = logged_in_client(educator).get(
        _cohort_history_url(cohort), {"history-export": "csv"}
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
