"""The learner page's data table panels: educator_interface/panels/learner/data_table_panels.py.

The Overview tab's Cohorts and Registrations cards, and the History tab with its
CSV export.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from uuid import uuid4

import lxml.html
import pytest

from django.test import Client
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import (
    record_entry,
)
from freedom_ls.content_engine.factories import (
    CourseFactory,
)
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.tests.helpers import (
    QUERY_BUDGET,
    _card_summary,
    _export_audit_csv,
    _get_document,
    _history_entry,
    _history_export_url,
    _history_rows,
    _interface_url,
    _learner_page,
    _record_run,
    _row_details,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import (
    move_between_cohorts,
    register_for_course,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortMembership,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.retire import retire

if TYPE_CHECKING:
    pass


@pytest.mark.django_db
def test_the_learner_cohorts_card_shows_the_join_date(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    membership = CohortMembershipFactory(
        learner=learner, cohort=CohortFactory(organisation=organisation)
    )
    CohortMembership.objects.filter(pk=membership.pk).update(
        created_at=datetime(2024, 3, 5, tzinfo=UTC)
    )

    document = _learner_page(staff_client, learner, "overview")

    (table,) = document.cssselect("#cohorts-table")
    assert "5 Mar 2024, 00:00" in " ".join(table.text_content().split())


@pytest.mark.django_db
def test_the_registrations_card_names_an_individual_registration_individual(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "Individual" in row.text_content()


@pytest.mark.django_db
def test_the_registrations_card_names_the_cohort_of_a_cohort_registration(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "via Evening group" in row.text_content()


@pytest.mark.django_db
def test_a_registration_rows_button_sits_in_the_rows_item_footer(
    staff_client: Client,
):
    """The Deactivate button sat in the row's trailing slot beside the badge.

    It belongs in the row's item footer under the title, and the badge stays
    in the trailing slot, outside the footer.
    """
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Geometry")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    (footer,) = row.cssselect("[data-item-footer]")
    assert "Deactivate" in footer.text_content()
    assert "Individual" not in footer.text_content()
    assert not row.cssselect("[data-testid='registration-action-slot']")


@pytest.mark.django_db
def test_a_registration_row_without_an_action_has_no_item_footer(
    staff_client: Client,
):
    """A cohort registration has no button, so its row renders no empty footer."""
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert not row.cssselect("[data-item-footer]")


@pytest.mark.django_db
def test_the_registrations_list_shows_no_list_markers(staff_client: Client):
    """The theme bullets and indents bare lists, so the card's rows sat 24px in."""
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "list-none" in row.getparent().get("class").split()


@pytest.mark.django_db
def test_the_registrations_card_shows_an_inactive_individual_registration_inactive(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra"), is_active=False
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    assert "Inactive" in row.text_content()


@pytest.mark.django_db
def test_the_registrations_card_leaves_out_a_course_from_an_inactive_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, is_active=False)
    CohortMembershipFactory(learner=learner, cohort=cohort)
    CohortCourseRegistrationFactory(
        cohort=cohort, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    assert not document.cssselect("[data-testid='registration-row']")


@pytest.mark.django_db
def test_the_history_tab_renders_its_empty_state(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())

    response = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        )
    )

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


@pytest.mark.django_db
def test_the_history_tab_lists_entries_naming_the_learner_only(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other = LearnerFactory(organisation=organisation)
    _history_entry(learner, actor_label="Ada Admin")
    _history_entry(other, actor_label="Someone Else")

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [(row[1], row[2]) for row in rows] == [("Ada Admin", "Learner deactivated")]


@pytest.mark.django_db
def test_the_history_tab_lists_the_newest_entry_first(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    now = timezone.now()
    _history_entry(learner, reason="older", created_at=now - timedelta(hours=1))
    _history_entry(learner, reason="newer", created_at=now)

    document = _learner_page(staff_client, learner, "history")

    assert _row_details(document, "[data-tab-set]") == ["Reason newer", "Reason older"]


@pytest.mark.django_db
def test_the_history_tab_pages_stably_when_entries_share_a_timestamp(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    when = timezone.now()
    for number in range(26):
        _history_entry(learner, reason=f"entry {number}", created_at=when)

    first_document = _learner_page(staff_client, learner, "history")
    second_page = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        ),
        {"history-page": 2},
    )
    second_document = lxml.html.fromstring(second_page.content.decode())

    first = _row_details(first_document, "[data-tab-set]")
    second = _row_details(second_document, "[data-tab-set]")
    assert (len(first), len(second), len(set(first + second))) == (25, 1, 26)


@pytest.mark.django_db
def test_the_history_tab_names_the_system_when_there_is_no_actor(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor_label="")

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert rows[0][1] == "System"


@pytest.mark.django_db
def test_the_history_tab_escapes_user_derived_text(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor_label="<b>actor</b>", reason="<b>why</b>")

    response = staff_client.get(
        _interface_url(
            learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
        )
    )

    content = response.content.decode()
    assert "&lt;b&gt;actor&lt;/b&gt;" in content
    assert "&lt;b&gt;why&lt;/b&gt;" in content
    assert "<b>actor</b>" not in content


@pytest.mark.django_db
def test_a_history_row_has_three_cells_and_a_toggle_with_the_reason_in_its_detail(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="Asked to leave")

    document = _learner_page(staff_client, learner, "history")

    (row,) = document.cssselect("[data-tab-set] tbody tr:not([data-row-detail])")
    (detail,) = document.cssselect("[data-tab-set] tbody tr[data-row-detail]")
    toggle = row.cssselect("td button[aria-expanded]")
    cells = [cell.text_content().strip() for cell in row.cssselect("td")]
    assert (
        len(cells),
        cells[3],
        len(toggle),
        toggle[0].get("aria-controls"),
        detail.get("id"),
        "Asked to leave" in detail.text_content(),
        "Asked to leave" in row.text_content(),
    ) == (
        4,
        "Learner deactivated",
        1,
        detail.get("id"),
        detail.get("id"),
        True,
        False,
    )


@pytest.mark.django_db
def test_an_entry_with_no_description_reason_or_run_entries_has_no_toggle(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="")

    document = _learner_page(staff_client, learner, "history")

    assert (
        document.cssselect("[data-tab-set] tbody button[aria-expanded]"),
        document.cssselect("[data-tab-set] tbody tr[data-row-detail]"),
    ) == ([], [])


@pytest.mark.django_db
def test_the_when_cell_has_an_iso_datetime_and_reads_as_one_run_of_date_then_time(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, created_at=datetime(2026, 3, 4, 10, 14, tzinfo=UTC))

    document = _learner_page(staff_client, learner, "history")

    (time_element,) = document.cssselect("[data-tab-set] tbody time")
    stamp = datetime.fromisoformat(time_element.get("datetime"))
    assert (
        stamp.utcoffset() is not None,
        stamp == datetime(2026, 3, 4, 10, 14, tzinfo=UTC),
        " ".join(time_element.text_content().split()).startswith("4 Mar 2026, "),
        # The date and the time share a colour.
        time_element.cssselect(".text-muted"),
    ) == (True, True, True, [])


@pytest.mark.django_db
def test_the_history_tab_shows_the_code_of_a_deactivated_action(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=learner, organisation=learner.organisation, action="widget.exploded"
    )

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert rows[0][2] == "widget.exploded"


@pytest.mark.django_db
def test_a_cohort_admin_gets_no_history_tab_and_a_404_on_its_url(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)
    client = logged_in_client(educator)

    document = _get_document(
        client, _interface_url(organisation.slug, f"learners/{learner.pk}")
    )
    response = client.get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/history")
    )

    (nav,) = document.cssselect("nav[aria-label='Learner sections']")
    hrefs = [a.get("href").rsplit("/", 1)[-1] for a in nav.cssselect("a")]
    assert ("history" in hrefs, response.status_code) == (False, 404)


@pytest.mark.django_db
def test_an_admin_of_another_organisation_gets_a_404_on_the_history_tab(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other_organisation = OrganisationFactory()
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=other_organisation).user
    assign_role(grantor, admin, "organisation_admin", other_organisation)

    response = logged_in_client(admin).get(
        _interface_url(organisation.slug, f"learners/{learner.pk}/__tabs/history")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_history_tab_renders_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    for number in range(25):
        _history_entry(learner, reason=f"entry {number}")
    url = _interface_url(
        learner.organisation.slug, f"learners/{learner.pk}/__tabs/history"
    )

    with django_assert_max_num_queries(QUERY_BUDGET):
        staff_client.get(url)


@pytest.mark.django_db
def test_the_learner_history_export_holds_every_entry_naming_the_learner(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    other = LearnerFactory(organisation=organisation)
    for number in range(30):
        _history_entry(learner, reason=f"reason {number}")
    _history_entry(other, reason="not ours")

    header, rows, _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert header == [
        "When",
        "Who",
        "Actor email",
        "What",
        "Action",
        "Target",
        "Description",
        "Reason",
        "Run ID",
    ]
    assert (len(rows), "not ours" in {row[7] for row in rows}) == (30, False)


@pytest.mark.django_db
def test_the_learner_history_export_is_named_for_the_learner(staff_client: Client):
    learner = LearnerFactory(
        organisation=OrganisationFactory(),
        user__first_name="Ada",
        user__last_name="Able",
    )
    _history_entry(learner)

    _header, _rows, disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert disposition == (
        f'attachment; filename="history-ada-able-{timezone.localdate():%Y-%m-%d}.csv"'
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_gets_a_404_on_the_learner_history_export(
    mock_site_context, logged_in_client, role: str
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    learner = LearnerFactory(organisation=organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, role, cohort)

    response = logged_in_client(educator).get(
        _history_export_url(learner), {"history-export": "csv"}
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learner_history_export_neutralises_a_formula_and_keeps_unicode(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, reason="=1+1", target_label="Zoë Ångström")

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[7], row[5]) == ("'=1+1", "Zoë Ångström")


@pytest.mark.django_db
def test_the_learner_history_export_leaves_actor_email_empty_for_a_system_entry(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner, actor=None, actor_label="")

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[1], row[2]) == ("System", "")


@pytest.mark.django_db
def test_the_learner_history_export_leaves_actor_email_empty_for_a_deleted_actor(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    actor = UserFactory(email="gone@example.com")
    _history_entry(learner, actor=actor, actor_label="Gone Person")
    actor.delete()

    _header, (row,), _disposition = _export_audit_csv(
        staff_client, _history_export_url(learner)
    )

    assert (row[1], row[2]) == ("Gone Person", "")


@pytest.mark.django_db
def test_the_learner_history_toolbar_offers_the_csv_export(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner)

    document = _learner_page(staff_client, learner, "history")

    links = [
        a for a in document.cssselect("a") if a.text_content().strip() == "Export CSV"
    ]
    assert links
    assert all("history-export=csv" in a.get("href") for a in links)


@pytest.mark.django_db
def test_the_learner_history_export_records_one_entry_for_the_organisation(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Able"
    )
    for _ in range(3):
        _history_entry(learner)

    _export_audit_csv(staff_client, _history_export_url(learner))

    entry = AuditLogEntry.objects.get(action="audit_log.exported")
    assert (
        entry.actor_id,
        entry.target_object_id,
        entry.details,
    ) == (
        User.objects.get(is_superuser=True).pk,
        str(organisation.pk),
        {"scope": "learner", "scope_label": "Ada Able", "count": 3, "filters": ""},
    )


@pytest.mark.django_db
def test_the_learner_history_export_omits_its_own_entry_and_a_second_export_adds_another(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    _history_entry(learner)
    url = _history_export_url(learner)

    _header, first_rows, _disposition = _export_audit_csv(staff_client, url)
    _header, second_rows, _disposition = _export_audit_csv(staff_client, url)

    assert (
        len(first_rows),
        len(second_rows),
        AuditLogEntry.objects.filter(action="audit_log.exported").count(),
    ) == (1, 1, 2)


@pytest.mark.django_db
def test_a_cohort_rows_remove_and_move_triggers_name_the_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    CohortMembershipFactory(learner=learner, cohort=cohort)

    document = _learner_page(staff_client, learner, "overview")

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if f"?cohort={cohort.pk}" in button.get("hx-get")
    }
    assert labels == {"Remove from Evening group", "Move from Evening group"}


@pytest.mark.django_db
def test_a_move_shows_on_the_learner_history_tab_as_from_a_to_b(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == [
        "Learner moved between cohorts From Alpha to Beta"
    ]


@pytest.mark.django_db
def test_the_learner_history_card_shows_the_label_then_labelled_when_and_who(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    AuditLogEntryFactory(
        target=learner,
        organisation=learner.organisation,
        action="learner.deactivated",
        actor_label="Ada Admin",
        target_label="Lee Learner",
        reason="Asked to leave",
    )

    document = _learner_page(staff_client, learner, "history")

    (card,) = document.cssselect("[data-tab-set] ul > li")
    assert _card_summary(card) == (
        "Learner deactivated",
        ["When", "Who"],
        ["Ada Admin"],
        True,
    )


@pytest.mark.django_db
def test_a_learner_registration_shows_on_the_learner_history_tab(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    register_for_course(learner, CourseFactory(title="Algebra"))

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == ["Learner registered for course Algebra"]


@pytest.mark.django_db
def test_a_bulk_runs_entry_shows_on_the_learners_history_tab(staff_client: Client):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    _record_run(organisation, [learner], uuid4())

    rows = _history_rows(_learner_page(staff_client, learner, "history"))

    assert [row[2] for row in rows] == ["Learner deactivated"]


@pytest.mark.django_db
def test_the_history_tab_names_a_nameless_actor_by_their_email(staff_client: Client):
    learner = LearnerFactory(organisation=OrganisationFactory())
    actor = UserFactory(first_name="", last_name="", email="nameless@example.com")
    record_entry(
        action="learner.deactivated",
        actor=actor,
        target=learner,
        target_label=learner.user.display_name,
        organisation=learner.organisation,
    )

    document = _learner_page(staff_client, learner, "history")

    # The name beside the avatar; the avatar's initial is aria-hidden.
    names = [
        span.text_content().strip()
        for span in document.cssselect(
            "[data-tab-set] tbody tr:not([data-row-detail]) span.truncate"
        )
    ]
    assert names == ["nameless@example.com"]


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_a_learners_history_tab_shows_the_actors_picture(
    staff_client: Client,
) -> None:
    actor = cast(User, UserFactory(with_profile_picture=True))
    learner = LearnerFactory()
    _history_entry(learner, actor=actor, actor_label=actor.display_name)

    document = _learner_page(staff_client, learner, "history")

    sources = [
        image.get("src") for image in document.cssselect("img[data-profile-picture]")
    ]
    assert actor.profile_picture_url in sources


@pytest.mark.django_db
def test_the_registrations_card_marks_a_retired_course_with_a_retired_badge(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=retire(cast(Course, CourseFactory(title="Algebra")))
    )

    document = _learner_page(staff_client, learner, "overview")

    (row,) = document.cssselect("[data-testid='registration-row']")
    (badge,) = row.cssselect("[data-testid='retired-badge']")
    assert badge.text_content().strip() == "Retired"


@pytest.mark.django_db
def test_the_registrations_card_marks_a_live_course_with_no_retired_badge(
    staff_client: Client,
):
    learner = LearnerFactory(organisation=OrganisationFactory())
    LearnerCourseRegistrationFactory(
        learner=learner, course=CourseFactory(title="Algebra")
    )

    document = _learner_page(staff_client, learner, "overview")

    assert document.cssselect("[data-testid='retired-badge']") == []
