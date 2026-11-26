"""The audit log tables: filter parameters and the page they render."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import lxml.html
import pytest
import time_machine
from pytest_django.fixtures import DjangoAssertNumQueries

from django.contrib import admin
from django.http import QueryDict
from django.test import Client, RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.audit_log.models import AuditLogEntry
from freedom_ls.audit_log.writer import (
    record_entry,
    record_run_summary,
)
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    AuditLogEntryTable,
)
from freedom_ls.educator_interface.tests.helpers import (
    QUERY_BUDGET,
    _audit_log_document,
    _audit_log_rows,
    _audit_log_url,
    _export_audit_csv,
    _get_document,
    _history_entry,
    _history_export_url,
    _history_rows,
    _interface_url,
    _learner_page,
    _record_run,
    _row_details,
    _visible_text,
    get_interface_page,
    organisation_admin_viewer,
    page_after_adding_rows,
    profile_picture_sources,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    LearnerFactory,
    StaffMemberFactory,
)
from freedom_ls.learner_progress.force_delete import force_delete_users
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

pytestmark = pytest.mark.usefixtures("_site_context")


@pytest.mark.django_db
def test_the_audit_log_filters_on_the_when_parameter(audit_request):
    request, organisation = audit_request
    recent = AuditLogEntryFactory(target=organisation)
    with time_machine.travel(datetime.now(UTC) - timedelta(days=30), tick=False):
        AuditLogEntryFactory(target=organisation)
    request.GET = QueryDict("audit-when=7d")

    query = AuditLogEntryTable.parse_query(request, "audit")
    rows = AuditLogEntryTable.filter_queryset(
        request,
        AuditLogEntry.objects.filter(organisation=organisation),
        query,
    )

    assert list(rows) == [recent]


def _audit_row_cells(
    document: lxml.html.HtmlElement, target_label: str
) -> dict[str, lxml.html.HtmlElement]:
    """The Who and Target cells of the Audit log row whose Target reads `target_label`."""
    for row in document.cssselect("tbody tr:not([data-row-detail])"):
        cells = row.cssselect("td")
        if _visible_text(cells[4]).endswith(target_label):
            return {"who": cells[2], "target": cells[4]}
    raise AssertionError(f"no Audit log row targets {target_label!r}")


def _avatar_slot(cell: lxml.html.HtmlElement) -> str | None:
    """The `panel-avatar-N` class of the initials circle in `cell`, if it has one."""
    for element in cell.iter():
        for name in (element.get("class") or "").split():
            if name.startswith("panel-avatar-"):
                return name
    return None


def _add_audit_entries_with_pictures(organisation: Organisation, count: int) -> None:
    for _ in range(count):
        actor = cast(User, UserFactory(with_profile_picture=True))
        target = cast(User, UserFactory(with_profile_picture=True))
        AuditLogEntryFactory(
            organisation=organisation,
            actor=actor,
            actor_label=actor.display_name,
            target=target,
            target_label=target.display_name,
        )


@pytest.mark.django_db
def test_the_audit_log_shows_when_as_day_month_year_and_24_hour_time(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, created_at=datetime(2026, 11, 3, 7, 37, tzinfo=UTC)
    )

    rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(organisation)))

    assert " ".join(rows[0][0].split()) == "3 Nov 2026, 07:37"


@pytest.mark.django_db
def test_the_audit_log_lists_only_the_request_organisations_entries(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    other = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours", actor_label="Ada")
    AuditLogEntryFactory(target=other, target_label="Theirs", actor_label="Bob")

    rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(organisation)))

    assert [row[3] for row in rows] == ["Ours"]


@pytest.mark.django_db
def test_a_site_admin_sees_each_organisations_own_entries(staff_client: Client):
    first = OrganisationFactory()
    second = OrganisationFactory()
    AuditLogEntryFactory(target=first, target_label="First entry")
    AuditLogEntryFactory(target=second, target_label="Second entry")

    first_rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(first)))
    second_rows = _audit_log_rows(_get_document(staff_client, _audit_log_url(second)))

    assert ([r[3] for r in first_rows], [r[3] for r in second_rows]) == (
        ["First entry"],
        ["Second entry"],
    )


@pytest.mark.django_db
def test_the_audit_log_target_column_reads_the_target_label(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Spring cohort",
        actor_label="Ada Admin",
        reason="because",
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    headers = [th.text_content().strip() for th in document.cssselect("thead th")]
    (row,) = _audit_log_rows(document)
    assert headers == ["Details", "When", "Who", "What", "Target"]
    assert row[1:4] == ["Ada Admin", "Cohort created", "Spring cohort"]
    assert _row_details(document, "body") == ["Reason because"]


@pytest.mark.django_db
def test_the_audit_row_toggle_is_named_by_the_label_not_the_action_code(
    staff_client: Client,
):
    """The row-detail toggle used to be named after the raw action code."""
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Spring cohort",
        reason="because",
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    (toggle,) = document.cssselect("tbody button[aria-label^='More about']")
    assert toggle.get("aria-label") == "More about Cohort created: Spring cohort"


@pytest.mark.django_db
def test_the_audit_log_renders_its_empty_state(staff_client: Client):
    organisation = OrganisationFactory()

    response = staff_client.get(_audit_log_url(organisation))

    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names


@pytest.mark.django_db
def test_the_audit_log_escapes_a_target_label_in_the_table_and_the_card(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="<b>bold</b>")

    html = staff_client.get(_audit_log_url(organisation)).content.decode()

    assert "&lt;b&gt;bold&lt;/b&gt;" in html
    assert "<b>bold</b>" not in html
    assert html.count("&lt;b&gt;bold&lt;/b&gt;") >= 2


@pytest.mark.django_db
def test_the_audit_log_filters_narrow_by_who_what_and_when(staff_client: Client):
    organisation = OrganisationFactory()
    ada = UserFactory(first_name="Ada", last_name="Admin")
    AuditLogEntryFactory(
        target=organisation, actor=ada, action="cohort.created", target_label="Match"
    )
    AuditLogEntryFactory(
        target=organisation,
        actor=ada,
        action="role.assigned",
        target_label="Wrong action",
    )
    AuditLogEntryFactory(
        target=organisation,
        actor=None,
        action="cohort.created",
        target_label="Wrong actor",
    )

    document = _get_document(
        staff_client,
        f"{_audit_log_url(organisation)}?audit_log-who={ada.pk}&audit_log-what=cohort.created&audit_log-when=today",
    )

    assert [row[3] for row in _audit_log_rows(document)] == ["Match"]


@pytest.mark.django_db
def test_a_tampered_filter_value_renders_the_unfiltered_list(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="One")
    AuditLogEntryFactory(target=organisation, target_label="Two")

    document = _get_document(
        staff_client,
        f"{_audit_log_url(organisation)}?audit_log-who=not-a-user&audit_log-what=bogus.code&audit_log-when=forever",
    )

    assert len(_audit_log_rows(document)) == 2


@pytest.mark.django_db
def test_the_filtered_audit_log_empty_state_offers_a_clear_link(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, action="cohort.created")

    response = staff_client.get(
        f"{_audit_log_url(organisation)}?audit_log-what=role.assigned"
    )

    html = response.content.decode()
    template_names = [t.name for t in response.templates]
    assert "panel_framework/partials/table_empty.html" in template_names
    assert "No entries match these filters." in html
    assert "Clear filters" in html


@pytest.mark.django_db
def test_a_bulk_run_is_one_audit_log_row_listing_fifty_entries_and_the_rest(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learners = [LearnerFactory(organisation=organisation) for _ in range(60)]
    _record_run(organisation, learners, uuid4(), target_label="<b>bold</b>")

    response = staff_client.get(_audit_log_url(organisation))

    document = lxml.html.fromstring(response.content)
    (row,) = _audit_log_rows(document)
    (detail,) = document.cssselect("tbody tr[data-row-detail]")
    (card_detail,) = document.cssselect("li [data-row-detail]")
    html = response.content.decode()
    assert (
        row[2].startswith("Bulk action completed"),
        "60 changed, 0 skipped, 0 failed" in " ".join(detail.text_content().split()),
        "60 changed, 0 skipped, 0 failed"
        in " ".join(card_detail.text_content().split()),
        len(detail.cssselect("li")),
        "and 10 more" in detail.text_content(),
        "<b>bold</b>" in html,
        "&lt;b&gt;bold&lt;/b&gt;" in html,
    ) == (True, True, True, 50, True, False, True)


@pytest.mark.django_db
def test_a_run_in_another_organisation_with_the_same_run_id_is_not_listed(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    other = OrganisationFactory()
    run_id = uuid4()
    _record_run(organisation, [LearnerFactory(organisation=organisation)], run_id)
    _record_run(
        other,
        [LearnerFactory(organisation=other), LearnerFactory(organisation=other)],
        run_id,
    )

    document = _get_document(staff_client, _audit_log_url(organisation))

    (detail,) = document.cssselect("tbody tr[data-row-detail]")
    assert len(detail.cssselect("li")) == 1


@pytest.mark.django_db
def test_the_audit_log_renders_three_runs_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    for _ in range(3):
        _record_run(organisation, [learner] * 5, uuid4())

    with django_assert_max_num_queries(QUERY_BUDGET):
        response = staff_client.get(_audit_log_url(organisation))

    assert len(_audit_log_rows(lxml.html.fromstring(response.content))) == 3


@pytest.mark.django_db
def test_the_system_actor_shows_the_settings_icon_and_no_chip(staff_client: Client):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(target=organisation, target_label="Ours", actor_label="")

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    who = cells["who"]
    assert (
        len(who.cssselect("svg[data-icon='settings']")),
        _visible_text(who),
        _avatar_slot(who),
    ) == (1, "System", None)


@pytest.mark.django_db
def test_a_deleted_actor_shows_the_user_icon_beside_the_stored_name(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        target=organisation, target_label="Ours", actor=None, actor_label="Gone Person"
    )

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    who = cells["who"]
    assert (
        len(who.cssselect("svg[data-icon='user']")),
        _visible_text(who),
        _avatar_slot(who),
    ) == (1, "Gone Person", None)


@pytest.mark.django_db
@pytest.mark.parametrize("learner_is_active", [True, False])
def test_a_person_target_has_the_same_avatar_colour_as_that_person_as_actor(
    staff_client: Client, learner_is_active: bool
):
    organisation = OrganisationFactory()
    user = UserFactory(first_name="Pat", last_name="Person")
    learner = LearnerFactory(
        organisation=organisation, user=user, is_active=learner_is_active
    )
    member = StaffMemberFactory(organisation=organisation, user=user)
    AuditLogEntryFactory(
        target=organisation,
        target_label="As actor",
        actor=user,
        actor_label="Pat Person",
    )
    for target, label in (
        (user, "User target"),
        (learner, "Learner target"),
        (member, "Member target"),
    ):
        AuditLogEntryFactory(
            target=target,
            target_label=label,
            organisation=organisation,
            action="learner.deactivated",
        )

    document = _audit_log_document(staff_client, organisation)

    actor_slot = _avatar_slot(_audit_row_cells(document, "As actor")["who"])
    target_cells = [
        _audit_row_cells(document, label)["target"]
        for label in ("User target", "Learner target", "Member target")
    ]
    assert actor_slot is not None
    assert [_avatar_slot(cell) for cell in target_cells] == [actor_slot] * 3
    assert [len(cell.cssselect("[aria-hidden='true']")) for cell in target_cells] == [
        1
    ] * 3


@pytest.mark.django_db
def test_the_learners_list_avatar_colours_match_the_audit_log_for_the_same_people(
    staff_client: Client,
):
    """The learners list keyed the avatar on the learner row's pk, so people
    were different colours there than in the audit log, which keys on the user.
    Many people are checked because any one pair could match by chance."""
    organisation = OrganisationFactory()
    names = [f"Person{letter}" for letter in "ABCDEFGH"]
    for name in names:
        user = UserFactory(first_name=name, last_name="Tester")
        LearnerFactory(organisation=organisation, user=user)
        AuditLogEntryFactory(
            target=organisation, target_label=name, actor=user, actor_label=name
        )

    audit_document = _audit_log_document(staff_client, organisation)
    audit_slots = [
        _avatar_slot(_audit_row_cells(audit_document, name)["who"]) for name in names
    ]
    list_document = _get_document(
        staff_client, _interface_url(organisation.slug, "learners")
    )
    list_slots = []
    for name in names:
        (row,) = [
            row
            for row in list_document.cssselect("tbody tr")
            if name in row.text_content()
        ]
        list_slots.append(_avatar_slot(row))

    assert list_slots == audit_slots


@pytest.mark.django_db
def test_a_learner_target_whose_row_was_deleted_shows_the_user_icon_and_stored_label(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    AuditLogEntryFactory(
        target=learner,
        target_label="Gone Learner",
        organisation=organisation,
        action="learner.deactivated",
    )
    learner.delete()

    cells = _audit_row_cells(
        _audit_log_document(staff_client, organisation), "Gone Learner"
    )

    target = cells["target"]
    assert (len(target.cssselect("svg[data-icon='user']")), _avatar_slot(target)) == (
        1,
        None,
    )


@pytest.mark.django_db
def test_a_cohort_target_renders_plain_text_with_no_circle(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    AuditLogEntryFactory(
        target=cohort, target_label="Spring cohort", organisation=organisation
    )

    cells = _audit_row_cells(
        _audit_log_document(staff_client, organisation), "Spring cohort"
    )

    target = cells["target"]
    assert (len(target.cssselect("[aria-label]")), _avatar_slot(target)) == (0, None)


@pytest.mark.django_db
def test_a_chip_for_a_user_with_no_name_takes_its_initials_from_the_email_label(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    user = UserFactory(first_name="", last_name="")
    AuditLogEntryFactory(
        target=organisation,
        target_label="Ours",
        actor=user,
        actor_label="zed@example.com",
    )

    cells = _audit_row_cells(_audit_log_document(staff_client, organisation), "Ours")

    assert _visible_text(cells["who"]).split()[0] == "Z"


@pytest.mark.django_db
def test_a_person_label_with_markup_renders_escaped(staff_client: Client):
    organisation = OrganisationFactory()
    user = UserFactory()
    AuditLogEntryFactory(
        target=organisation,
        target_label="Ours",
        actor=user,
        actor_label="<b>bold</b>",
    )

    response = staff_client.get(_audit_log_url(organisation))

    html = response.content.decode()
    assert ("<b>bold</b>" in html, "&lt;b&gt;bold&lt;/b&gt;" in html) == (False, True)


@pytest.mark.django_db
def test_the_audit_log_renders_three_runs_of_learner_entries_within_a_query_budget(
    staff_client: Client, django_assert_max_num_queries
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    for _ in range(3):
        _record_run(
            organisation, [learner] * 5, uuid4(), target_label=learner.user.email
        )

    with django_assert_max_num_queries(QUERY_BUDGET + 3):
        response = staff_client.get(_audit_log_url(organisation))

    assert len(_audit_log_rows(lxml.html.fromstring(response.content))) == 3


@pytest.mark.django_db
def test_the_audit_log_what_filter_is_a_grouped_checklist_with_one_apply(
    staff_client: Client,
):
    """Many actions as a chip cloud were unreadable; the filter is a checkbox
    per action under its group, applied once, in the toolbar and the sheet."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _audit_log_url(organisation))

    # The popover form in the toolbar; the sheet holds its own copy.
    (toolbar_form,) = [
        form
        for form in document.cssselect("details form[hx-get]")
        if form.cssselect("input[type='checkbox'][name='audit_log-what']")
    ]
    legends = [
        legend.text_content().strip() for legend in toolbar_form.cssselect("legend")
    ]
    assert legends == [
        "Learners",
        "Cohort membership",
        "Course registrations",
        "Course progress",
        "Cohorts",
        "Staff and roles",
        "Applications",
        "Other",
    ]
    assert toolbar_form.xpath(".//button[@type='submit'][normalize-space()='Apply']")
    assert "Learner added to cohort" in toolbar_form.text_content()
    (sheet,) = document.cssselect("dialog#audit_log-sheet")
    summaries = [
        summary.text_content().strip() for summary in sheet.cssselect("details summary")
    ]
    assert summaries == legends
    assert not sheet.cssselect("label.rounded-full")


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_the_audit_log_shows_the_who_and_target_pictures() -> None:
    organisation = OrganisationFactory()
    actor = cast(User, UserFactory(with_profile_picture=True))
    target = cast(User, UserFactory(with_profile_picture=True))
    AuditLogEntryFactory(
        organisation=organisation,
        actor=actor,
        actor_label=actor.display_name,
        target=target,
        target_label=target.display_name,
    )

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    sources = profile_picture_sources(content)
    assert actor.profile_picture_url in sources
    assert target.profile_picture_url in sources


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_the_audit_log_names_a_person_without_a_picture_by_initials_alone() -> None:
    organisation = OrganisationFactory()
    person = cast(User, UserFactory())
    AuditLogEntryFactory(
        organisation=organisation,
        actor=person,
        actor_label=person.display_name,
        target=person,
        target_label=person.display_name,
    )

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    assert profile_picture_sources(content) == []
    assert 'src="None"' not in content


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_the_audit_log_shows_a_deleted_actor_and_a_system_entry_without_a_picture() -> (
    None
):
    organisation = OrganisationFactory()
    AuditLogEntryFactory(
        organisation=organisation,
        actor=None,
        actor_label="Gone Person",
        target=organisation,
        target_label="Spring cohort",
    )
    AuditLogEntryFactory(
        organisation=organisation,
        actor=None,
        actor_label="",
        target=organisation,
        target_label="Autumn cohort",
    )

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    assert profile_picture_sources(content) == []
    assert "Gone Person" in content
    assert "System" in content


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_the_audit_log_stops_showing_a_picture_once_it_is_removed() -> None:
    organisation = OrganisationFactory()
    actor = cast(User, UserFactory(with_profile_picture=True))
    AuditLogEntryFactory(
        organisation=organisation,
        actor=actor,
        actor_label=actor.display_name,
        target=organisation,
    )
    actor.profile_picture.delete()

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    assert profile_picture_sources(content) == []


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_a_bulk_run_entry_in_the_audit_log_shows_its_actors_picture() -> None:
    organisation = OrganisationFactory()
    actor = cast(User, UserFactory(with_profile_picture=True))
    learner = LearnerFactory(organisation=organisation)
    run_id = uuid4()
    record_entry(
        action="learner.deactivated",
        actor=actor,
        target=learner,
        target_label="Spring cohort",
        organisation=organisation,
        run_id=run_id,
    )
    record_run_summary(
        action="bulk_action.completed",
        run_id=run_id,
        organisation=organisation,
        actor=None,
        counts={"changed": 1, "skipped": 0, "failed": 0},
    )

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    assert actor.profile_picture_url in profile_picture_sources(content)


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_a_bulk_run_entry_by_the_runs_own_actor_names_them_without_a_second_avatar() -> (
    None
):
    organisation = OrganisationFactory()
    actor = cast(User, UserFactory(with_profile_picture=True))
    learner = LearnerFactory(organisation=organisation)
    run_id = uuid4()
    record_entry(
        action="learner.deactivated",
        actor=actor,
        target=learner,
        target_label="Spring cohort",
        organisation=organisation,
        run_id=run_id,
    )
    record_run_summary(
        action="bulk_action.completed",
        run_id=run_id,
        organisation=organisation,
        actor=actor,
        counts={"changed": 1, "skipped": 0, "failed": 0},
    )

    content = get_interface_page(
        organisation, "audit-log", organisation_admin_viewer(organisation)
    )

    entries = lxml.html.fromstring(content).cssselect("dd ul.list-none > li")
    assert entries
    for entry in entries:
        actor_chip = entry.cssselect("li > div")[0]
        assert actor.display_name in actor_chip.text_content()
        assert actor_chip.cssselect("[class*='panel-avatar-']") == []
    assert actor.profile_picture_url in profile_picture_sources(content)


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_more_audit_entries_with_pictures_cost_no_more_queries(
    django_assert_max_num_queries: DjangoAssertNumQueries,
) -> None:
    content = page_after_adding_rows(
        OrganisationFactory(),
        "audit-log",
        _add_audit_entries_with_pictures,
        django_assert_max_num_queries,
    )

    assert len(profile_picture_sources(content)) >= 10


@pytest.mark.django_db
def test_an_export_entry_shows_on_the_audit_log_and_not_on_the_learner_history(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(
        organisation=organisation, user__first_name="Ada", user__last_name="Able"
    )
    _history_entry(learner)
    _export_audit_csv(staff_client, _history_export_url(learner))

    audit_rows = _audit_log_rows(
        _get_document(staff_client, _audit_log_url(organisation))
    )
    history_rows = _history_rows(_learner_page(staff_client, learner, "history"))

    exported = [row for row in audit_rows if "Audit log exported" in row[2]]
    assert (
        len(exported),
        "Ada Able: 1 entry" in exported[0][2],
        len(history_rows),
    ) == (
        1,
        True,
        1,
    )


@pytest.mark.django_db
def test_a_force_deleted_learner_appears_in_their_own_organisations_audit_log(
    staff_client: Client,
) -> None:
    user = cast(User, UserFactory())
    organisation = OrganisationFactory()
    other = OrganisationFactory()
    LearnerFactory(user=user, organisation=organisation)
    LearnerFactory(user=user, organisation=other)
    actor = UserFactory(superuser=True)
    request = RequestFactory().post("/")
    request.user = actor

    force_delete_users(
        [user],
        actor=actor,
        reason="Erasure requested",
        request=request,
        admin_site=admin.site,
    )

    ours = _audit_log_rows(_get_document(staff_client, _audit_log_url(organisation)))
    theirs = _audit_log_rows(_get_document(staff_client, _audit_log_url(other)))
    assert len(ours) == 1
    assert "Learner force deleted" in " ".join(ours[0])
    assert len(theirs) == 1
