"""The educator interface's section configs and the pages they render."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest

from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.urls import NoReverseMatch, reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.comms.factories import NotificationFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
)
from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.educator_interface.panels.audit_log.data_tables import (
    OrganisationAuditLogTable,
)
from freedom_ls.educator_interface.panels.cohort.data_table_panels import (
    CohortHistoryPanel,
)
from freedom_ls.educator_interface.panels.cohort.data_tables import (
    CohortCourseRegistrationDataTable,
    CohortDataTable,
    LearnerCohortDataTable,
)
from freedom_ls.educator_interface.panels.course.data_tables import (
    CourseCohortRegistrationDataTable,
    CourseDataTable,
    CourseLearnerRegistrationDataTable,
)
from freedom_ls.educator_interface.panels.learner.bulk_actions import (
    DeactivateLearnersBulkAction,
)
from freedom_ls.educator_interface.panels.learner.data_table_panels import (
    LearnerHistoryPanel,
)
from freedom_ls.educator_interface.panels.learner.data_tables import (
    CohortLearnerDataTable,
    LearnerDataTable,
)
from freedom_ls.educator_interface.panels.staff.data_tables import StaffDataTable
from freedom_ls.educator_interface.tests.helpers import (
    _add_member,
    _audit_log_rows,
    _audit_log_url,
    _cohort_history_tab,
    _cohort_history_url,
    _cohort_page,
    _export_audit_csv,
    _get_document,
    _header_of,
    _history_entry,
    _history_export_url,
    _history_rows,
    _interface_url,
    _learner_page,
    _msg_conversation,
    _msg_educator,
    _msg_learner,
    _msg_url,
    _notes_for,
    _shared_and_own_course_world,
    _shared_by_notes_by_row,
    get_interface_page,
    messages_section,
    organisation_admin_viewer,
    page_after_adding_rows,
    profile_picture_sources,
)
from freedom_ls.educator_interface.tests.interface_walk import (
    WalkedPanel,
    walk_interface,
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
)
from freedom_ls.learner_management.models import (
    Cohort,
)
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation
from freedom_ls.panel_framework.bulk_runs import run_bulk_action
from freedom_ls.panel_framework.models import BulkActionRun
from freedom_ls.panel_framework.tables import DataTable

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


@pytest.mark.django_db
def test_cohort_detail_page_has_overview_learners_courses_report_settings_and_history_tabs(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    for _ in range(2):
        CohortMembershipFactory(
            cohort=cohort, learner=LearnerFactory(organisation=organisation)
        )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    links = nav.cssselect("a")
    assert [link.get("href").rsplit("/", 1)[-1] for link in links] == [
        "overview",
        "learners",
        "courses",
        "report",
        "settings",
        "history",
    ]
    assert links[0].get("aria-current") == "page"
    assert links[1].get("aria-current") is None
    assert links[1].text_content().split() == ["Learners", "2"]
    headings = [
        h.text_content().strip() for h in document.cssselect("[data-tab-set] h2")
    ]
    assert headings == [
        "Details",
        "Course completion",
        "Needs attention",
    ]


@pytest.mark.django_db
def test_the_learners_tab_count_excludes_a_removed_member(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    CohortMembershipFactory(
        cohort=cohort, learner=LearnerFactory(organisation=organisation)
    )
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(organisation=organisation, is_active=False),
    )

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    assert nav.cssselect("a")[1].text_content().split() == ["Learners", "1"]


@pytest.mark.django_db
def test_cohort_page_actions_sit_in_the_page_header_not_the_details_card(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")
    page_url = _interface_url(organisation.slug, f"cohorts/{cohort.pk}")

    document = _get_document(staff_client, page_url)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert not header.cssselect("button[hx-get]")
    (details_panel,) = document.cssselect("section[data-panel='details']")
    assert not details_panel.cssselect("footer")
    assert not details_panel.cssselect("button[hx-get]")

    settings = _get_document(staff_client, f"{page_url}/__tabs/settings")

    triggers = {button.get("hx-get") for button in settings.cssselect("button[hx-get]")}
    assert (
        f"{page_url}/__tabs/settings/__panels/status/__actions/deactivate" in triggers
    )
    assert f"{page_url}/__tabs/settings/__panels/name/__actions/edit" not in triggers
    (form,) = settings.cssselect("form#cohort-name-form")
    assert (
        form.get("hx-post")
        == f"{page_url}/__tabs/settings/__panels/name/__actions/edit"
    )
    (name,) = form.cssselect("input[name=name]")
    assert name.get("value") == "Evening group"
    assert name.get("autofocus") is None
    assert all(
        "btn-sm" in button.get("class").split()
        for button in settings.cssselect("section[data-panel='status'] footer .btn")
    )


@pytest.mark.django_db
def test_an_instance_page_marks_its_section_current_without_naming_the_instance(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (nav,) = document.cssselect("#sidebar-nav")
    (current,) = nav.cssselect("a[aria-current]")
    assert current.text_content().strip().startswith("Cohorts")
    assert current.get("aria-current") == "true"
    assert "Evening group" not in nav.text_content()


@pytest.mark.django_db
def test_an_instance_page_offers_a_back_link_to_its_list(staff_client: Client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Evening group")

    document = _get_document(
        staff_client, _interface_url(organisation.slug, f"cohorts/{cohort.pk}")
    )

    (back,) = document.cssselect("#breadcrumbs a")
    assert back.get("href") == _interface_url(organisation.slug, "cohorts")
    assert back.text_content().strip() == "Cohorts"


@pytest.mark.django_db
def test_a_list_page_shows_no_breadcrumb(staff_client: Client):
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    assert not document.cssselect("#breadcrumbs a")
    assert not document.cssselect("#breadcrumbs nav")


@pytest.mark.django_db
def test_navigation_toggle_shows_a_menu_icon_not_a_panel_chevron(
    staff_client: Client,
):
    """The content header's navigation toggle drew a chevron instead of a menu icon."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (icon,) = toggle.cssselect("svg")
    assert icon.get("data-icon") == "menu"


@pytest.mark.django_db
def test_navigation_toggle_sits_in_the_page_heading_row(staff_client: Client):
    """On mobile the toggle took a row of its own above the page heading."""
    organisation = OrganisationFactory()

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    (toggle,) = document.cssselect("button[aria-label='Open navigation panel']")
    (heading,) = document.cssselect("#main-content h1")
    assert toggle.getparent() is heading.getparent().getparent()


@pytest.mark.django_db
def test_organisation_root_page_still_offers_the_navigation_toggle(
    staff_client: Client,
):
    """The organisation root used to render a page with no heading of its
    own, leaving a phone with no way to open the navigation. It now sends the
    visitor to a section, and the page they land on offers the toggle."""
    organisation = OrganisationFactory()

    response = staff_client.get(_interface_url(organisation.slug, ""), follow=True)
    assert response.status_code == 200
    document = lxml.html.fromstring(response.content.decode())

    (toggle,) = document.cssselect(
        "#main-content button[aria-label='Open navigation panel']"
    )
    assert toggle.cssselect("svg[data-icon]")


@pytest.mark.django_db
def test_settings_tab_is_present_for_an_organisation_admin(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    admin = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, admin, "organisation_admin", organisation)

    document = _get_document(
        logged_in_client(admin),
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}"),
    )

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    assert "Settings" in [a.text_content().split()[0] for a in nav.cssselect("a")]


@pytest.mark.django_db
def test_settings_tab_answers_404_for_a_cohort_viewer(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_viewer", cohort)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, f"cohorts/{cohort.pk}/__tabs/settings")
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_an_active_cohort_header_has_no_badge_no_stats_and_no_buttons(
    staff_client: Client,
):
    """Active is the default, the tabs already count learners and courses, and
    the actions live in Settings, so the header is the name and the tabs."""
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    header = _header_of(_cohort_page(staff_client, cohort))

    assert "Active" not in header.text_content()
    assert "Learners" not in header.text_content()
    assert not header.cssselect(".btn")


@pytest.mark.django_db
def test_inactive_cohort_header_shows_the_inactive_badge(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory(), is_active=False)

    document = _cohort_page(staff_client, cohort)

    (heading,) = document.cssselect("#instance-title")
    header = heading.xpath("ancestor::*[contains(@class, 'justify-between')]")[0]
    assert "Inactive" in header.text_content().split()


@pytest.mark.django_db
def test_cohort_header_refreshes_its_counts_when_the_cohort_changes(
    staff_client: Client,
):
    """The header stats and tab counts stayed stale after a membership change
    because nothing re-fetched them when the cohort-changed event fired."""
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (refresher,) = document.cssselect("#instance-header [data-refresh-events]")
    assert refresher.get("data-refresh-events") == COHORT_CHANGED


@pytest.mark.django_db
def test_a_header_refresh_gets_the_header_alone(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())
    _add_member(cohort)

    response = staff_client.get(
        _interface_url(cohort.organisation.slug, f"cohorts/{cohort.pk}"),
        headers={"HX-Request": "true", "HX-Target": "instance-header"},
    )

    document = lxml.html.fromstring(response.content.decode())
    assert (
        document.get("id"),
        len(document.cssselect("[data-panel]")),
    ) == ("instance-header", 0)


@pytest.mark.django_db
def test_the_cohort_page_opens_on_the_overview_tab(staff_client: Client):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (nav,) = document.cssselect("nav[aria-label='Cohort sections']")
    (active,) = [a for a in nav.cssselect("a") if a.get("aria-current") == "page"]
    assert active.text_content().split()[0] == "Overview"


@pytest.mark.django_db
def test_needs_attention_card_renders_a_skeleton_that_fetches_its_body(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    (card,) = document.cssselect("section[data-panel='attention']")
    (region,) = card.cssselect("div[aria-busy='true']")
    (fetch,) = region.cssselect("[hx-trigger='load']")
    assert fetch.get("hx-get").endswith("/__panels/attention?loaded=1")


@pytest.mark.django_db
def test_overview_lists_details_completion_and_attention_in_order(
    staff_client: Client,
):
    cohort = CohortFactory(organisation=OrganisationFactory())

    document = _cohort_page(staff_client, cohort)

    panels = [
        s.get("data-panel")
        for s in document.cssselect("[data-tab-set] section[data-panel]")
    ]
    assert panels[:3] == ["details", "completion", "attention"]


@pytest.mark.django_db
def test_every_panel_under_the_cohort_page_refreshes_on_cohort_changed(
    mock_site_context: Site,
):
    organisation = OrganisationFactory()
    cohort_paths = [
        item
        for item in walk_interface(organisation)
        if isinstance(item, WalkedPanel)
        and item.path.startswith("cohorts/")
        and "/__" in item.path
        and "/__actions/" not in item.path
    ]

    missing = [
        item.path
        for item in cohort_paths
        if COHORT_CHANGED not in item.panel.refresh_events
    ]

    assert cohort_paths
    assert missing == []


@pytest.mark.django_db
def test_a_cohort_admin_gets_no_organisation_audit_log(
    mock_site_context, logged_in_client
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, "cohort_admin", cohort)

    response = logged_in_client(educator).get(
        _interface_url(organisation.slug, "audit-log")
    )

    assert response.status_code == 404


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
def test_a_members_page_renders_an_inactive_cohorts_row_without_any_action(
    staff_client: Client,
):
    cohort = CohortFactory(
        organisation=OrganisationFactory(), is_active=False, name="Dormant group"
    )
    learner = _add_member(cohort)

    document = _learner_page(staff_client, learner)

    (row,) = document.xpath("//tr[contains(., 'Dormant group')]")
    assert row.cssselect("button") == []


@pytest.mark.django_db
def test_the_add_to_cohort_picker_on_a_learners_page_offers_no_inactive_cohort(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.get(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        HTTP_HX_REQUEST="true",
    )

    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_the_add_to_cohort_picker_offers_no_inactive_cohort_after_a_submit_with_no_choice(
    staff_client: Client,
):
    """A submit with no cohort chosen used to re-render the select with the
    organisation's inactive cohorts, which the first render never offered."""
    organisation = OrganisationFactory()
    inactive = CohortFactory(organisation=organisation, is_active=False)
    learner = LearnerFactory(organisation=organisation)

    response = staff_client.post(
        _interface_url(
            organisation.slug, f"learners/{learner.pk}/__actions/add_to_cohort"
        ),
        {"cohort": ""},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 422
    assert str(inactive.pk) not in response.content.decode()


@pytest.mark.django_db
def test_a_members_page_renders_an_inactive_cohorts_row_with_no_move(
    staff_client: Client,
):
    cohort = CohortFactory(
        organisation=OrganisationFactory(), is_active=False, name="Dormant group"
    )
    learner = _add_member(cohort)

    document = _learner_page(staff_client, learner)

    (row,) = document.xpath("//tr[contains(., 'Dormant group')]")
    assert "__actions/move" not in lxml.html.tostring(row).decode()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["cohort_admin", "cohort_viewer"])
def test_a_cohort_role_holder_sees_no_administration_group(role_holder_client, role):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, role)

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    headings = [h.text_content().strip() for h in document.cssselect("#sidebar-nav h2")]
    assert headings == ["Teaching"]


@pytest.mark.django_db
def test_a_cohort_admin_still_sees_the_dashboard(role_holder_client):
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation)
    client = role_holder_client(cohort, "cohort_admin")

    response = client.get(_interface_url(organisation.slug, ""))

    assert response.status_code == 302
    assert response["Location"] == _interface_url(organisation.slug, "dashboard")


@pytest.mark.django_db
def test_a_move_shows_on_both_cohorts_and_the_learner_history_tabs(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    learner = LearnerFactory(organisation=organisation)
    source = CohortFactory(organisation=organisation, name="Alpha")
    destination = CohortFactory(organisation=organisation, name="Beta")
    CohortMembershipFactory(learner=learner, cohort=source)
    move_between_cohorts(learner, source, destination, actor=UserFactory())

    shown = [
        _history_rows(_cohort_history_tab(staff_client, source)),
        _history_rows(_cohort_history_tab(staff_client, destination)),
        _history_rows(_learner_page(staff_client, learner, "history")),
    ]

    assert [[row[2] for row in rows] for rows in shown] == [
        ["Learner moved between cohorts From Alpha to Beta"]
    ] * 3


# The educator interface has no Messages section: the conversation with a
# learner lives on the learner page.


@pytest.mark.django_db
@messages_section
@pytest.mark.parametrize("messaging_enabled", [True, False])
def test_the_messages_section_paths_are_404s(
    msg_client_for, settings, messaging_enabled
):
    settings.MESSAGING_ENABLED = messaging_enabled
    organisation = OrganisationFactory()
    educator = _msg_educator(organisation)
    learner = _msg_learner(organisation)
    conversation = _msg_conversation(educator, learner.user)
    client = msg_client_for(educator)

    assert client.get(_msg_url(organisation, "messages")).status_code == 404
    assert (
        client.get(_msg_url(organisation, f"messages/{conversation.pk}")).status_code
        == 404
    )


def test_the_unread_count_route_no_longer_exists():
    with pytest.raises(NoReverseMatch):
        reverse(
            "educator_interface:messages_unread_count",
            kwargs={"organisation_slug": "any"},
        )


# bulk run status, polled by the table a background run was started from.
# The route is the framework's; these cover its wiring into this interface
# (the organisation scope, the refresh event and the notification hooks).


def _run_for(user: User, organisation: Organisation, **fields: object):
    return BulkActionRun.objects.create(
        site=organisation.site,
        scope=organisation,
        requested_by=user,
        action_path=(
            f"{DeactivateLearnersBulkAction.__module__}."
            f"{DeactivateLearnersBulkAction.__name__}"
        ),
        table_key="learners",
        action_name="deactivate",
        keys=[str(LearnerFactory(organisation=organisation).pk) for _ in range(2)],
        **fields,
    )


def _run_status_url(organisation: Organisation, run: BulkActionRun) -> str:
    return reverse(
        "educator_interface:interface",
        kwargs={
            "organisation_slug": organisation.slug,
            "path_string": f"learners/__runs/{run.pk}",
        },
    )


@pytest.fixture
def run_world(logged_in_client: Callable[[User], Client], mock_site_context: Site):
    organisation = OrganisationFactory()
    requester = cast(User, UserFactory(superuser=True))
    return SimpleNamespace(
        organisation=organisation,
        requester=requester,
        client=logged_in_client(requester),
        run=_run_for(requester, organisation),
    )


def _poll(world: SimpleNamespace) -> _MonkeyPatchedWSGIResponse:
    client: Client = world.client
    return client.get(
        _run_status_url(world.organisation, world.run), HTTP_HX_REQUEST="true"
    )


@pytest.mark.django_db
def test_an_unfinished_run_answers_204(run_world: SimpleNamespace):
    response = _poll(run_world)

    assert (response.status_code, response.content) == (204, b"")


@pytest.mark.django_db
def test_a_finished_run_answers_the_result_modal_and_refreshes_the_table(
    run_world: SimpleNamespace, mock_site_context: Site
):
    run_bulk_action(str(run_world.run.pk), mock_site_context.pk)

    response = _poll(run_world)

    document = lxml.html.fromstring(response.content.decode())
    assert response.status_code == 200
    assert "2 learners changed." in document.text_content()
    assert json.loads(response["HX-Trigger"]) == {LEARNER_CHANGED: {"ids": []}}


@pytest.mark.django_db
def test_a_finished_run_marks_its_notification_read(
    run_world: SimpleNamespace, mock_site_context: Site
):
    run_bulk_action(str(run_world.run.pk), mock_site_context.pk)
    notification = NotificationFactory(
        user=run_world.requester,
        category="bulk_action.finished",
        target=run_world.run,
        data={"summary": "Deactivate finished: 2 learners changed."},
    )

    _poll(run_world)

    notification.refresh_from_db()
    assert notification.read_at is not None


@pytest.mark.django_db
def test_an_unfinished_run_leaves_its_notification_unread(
    run_world: SimpleNamespace,
):
    notification = NotificationFactory(
        user=run_world.requester,
        category="bulk_action.finished",
        target=run_world.run,
        data={"summary": "s"},
    )

    _poll(run_world)

    notification.refresh_from_db()
    assert notification.read_at is None


@pytest.mark.django_db
def test_a_run_is_a_404_for_another_user_of_the_organisation(
    run_world: SimpleNamespace, logged_in_client
):
    other = cast(User, UserFactory(superuser=True))

    response = logged_in_client(other).get(
        _run_status_url(run_world.organisation, run_world.run)
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_a_run_is_a_404_through_another_organisations_slug(
    run_world: SimpleNamespace,
):
    elsewhere = OrganisationFactory()

    response = run_world.client.get(_run_status_url(elsewhere, run_world.run))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_learners_bar_promotes_four_actions_and_lists_the_rest_with_the_destructive_one_last_under_more(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    LearnerFactory(organisation=organisation)

    document = _get_document(
        staff_client, _interface_url(organisation.slug, "learners")
    )

    def labels(selector: str) -> list[str]:
        return [
            " ".join(element.text_content().split())
            for element in document.cssselect(selector)
        ]

    assert labels("div[data-total-count] > div > fieldset > button[formaction]") == [
        "Add to cohort",
        "Deactivate",
        "Reactivate",
        "Register for a course",
    ]
    assert labels("fieldset > span [role='menu'] button[formaction]") == [
        "Deactivate a course registration",
        "Resend setup email",
        "Remove from cohort",
    ]


@pytest.mark.django_db
def test_the_cohorts_bar_promotes_all_four_actions_and_has_no_more_menu(
    staff_client: Client,
):
    organisation = OrganisationFactory()
    CohortFactory(organisation=organisation)

    document = _get_document(staff_client, _interface_url(organisation.slug, "cohorts"))

    def labels(selector: str) -> list[str]:
        return [
            " ".join(element.text_content().split())
            for element in document.cssselect(selector)
        ]

    assert labels("div[data-total-count] > div > fieldset > button[formaction]") == [
        "Register for a course",
        "Deactivate a course registration",
        "Deactivate",
        "Reactivate",
    ]
    assert labels("[role='menu'] button[formaction]") == []


EDUCATOR_TABLES: list[type[DataTable]] = [
    LearnerDataTable,
    CohortLearnerDataTable,
    CohortDataTable,
    LearnerCohortDataTable,
    CourseDataTable,
    CohortCourseRegistrationDataTable,
    CourseCohortRegistrationDataTable,
    CourseLearnerRegistrationDataTable,
    StaffDataTable,
    OrganisationAuditLogTable,
]


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_first_use_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_message.endswith(".")
    assert table.empty_message != DataTable.empty_message


@pytest.mark.parametrize("panel", [LearnerHistoryPanel, CohortHistoryPanel])
def test_a_history_panel_says_what_will_be_recorded(panel: type) -> None:
    assert panel.empty_message.endswith(".")
    assert panel.data_table.empty_no_results.endswith(".")


@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_the_no_results_message_is_a_sentence(table: type[DataTable]) -> None:
    assert table.empty_no_results.endswith(".")


@pytest.mark.django_db
@pytest.mark.parametrize("table", EDUCATOR_TABLES)
def test_a_filter_in_play_offers_to_clear_it(
    table: type[DataTable], mock_site_context: Site
) -> None:
    html = render_to_string(
        "panel_framework/partials/table_empty.html",
        {
            "any_filter_set": True,
            "empty_no_results": table.empty_no_results,
            "empty_message": table.empty_message,
            "clear_changes": {},
            "clear_search_changes": {},
            "page_url": "/x/",
            "base_url": "/x/",
            "region_id": "r",
        },
        request=RequestFactory().get("/x/"),
    )

    assert table.empty_no_results in html
    assert table.empty_message not in html
    assert "Clear filters" in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "target"),
    [
        ("cohort_admin", "audit_log"),
        ("cohort_viewer", "cohort_history"),
        ("cohort_viewer", "audit_log"),
    ],
)
def test_a_cohort_role_gets_a_404_on_the_exports_it_may_not_read(
    mock_site_context, logged_in_client, role: str, target: str
):
    organisation = OrganisationFactory()
    cohort = cast(Cohort, CohortFactory(organisation=organisation))
    grantor = LearnerFactory(user__superuser=True).user
    educator = LearnerFactory(user__staff=True, organisation=organisation).user
    assign_role(grantor, educator, role, cohort)
    url, key = (
        (_cohort_history_url(cohort), "history-export")
        if target == "cohort_history"
        else (_audit_log_url(organisation), "audit_log-export")
    )

    response = logged_in_client(educator).get(url, {key: "csv"})

    assert response.status_code == 404


# Profile pictures on the learners table, course registrations table, cohort settings panel and audit log.

PictureSurface = Callable[[Organisation, User], str]


def _learners_table(organisation: Organisation, person: User) -> str:
    LearnerFactory(organisation=organisation, user=person)
    return get_interface_page(
        organisation, "learners", organisation_admin_viewer(organisation)
    )


def _registrations_table(organisation: Organisation, person: User) -> str:
    course = CourseFactory()
    learner = LearnerFactory(organisation=organisation, user=person)
    LearnerCourseRegistrationFactory(learner=learner, course=course, is_active=True)
    return get_interface_page(
        organisation,
        f"courses/{course.pk}/__panels/learners",
        organisation_admin_viewer(organisation),
    )


def _cohort_settings(organisation: Organisation, person: User) -> str:
    cohort = CohortFactory(organisation=organisation)
    assign_role(UserFactory(superuser=True), person, "cohort_admin", cohort)
    return get_interface_page(
        organisation,
        f"cohorts/{cohort.pk}/__tabs/settings",
        organisation_admin_viewer(organisation),
    )


PICTURE_SURFACES = [
    pytest.param(_learners_table, id="learners-table"),
    pytest.param(_registrations_table, id="course-registrations-table"),
    pytest.param(_cohort_settings, id="cohort-settings"),
]


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_with_a_picture_shows_it(surface: PictureSurface) -> None:
    person = cast(User, UserFactory(with_profile_picture=True))

    content = surface(OrganisationFactory(), person)

    assert person.profile_picture_url in profile_picture_sources(content)


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
@pytest.mark.parametrize("surface", PICTURE_SURFACES)
def test_a_person_without_a_picture_shows_initials_alone(
    surface: PictureSurface,
) -> None:
    content = surface(OrganisationFactory(), cast(User, UserFactory()))

    assert profile_picture_sources(content) == []
    assert 'src="None"' not in content


def _add_learner_rows(organisation: Organisation, count: int) -> None:
    for _ in range(count):
        LearnerFactory(
            organisation=organisation, user=UserFactory(with_profile_picture=True)
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_site_context")
def test_more_learner_rows_with_pictures_cost_no_more_queries(
    django_assert_max_num_queries,
) -> None:
    content = page_after_adding_rows(
        OrganisationFactory(),
        "learners",
        _add_learner_rows,
        django_assert_max_num_queries,
    )

    assert len(profile_picture_sources(content)) >= 5


@pytest.mark.django_db
def test_learners_list_names_the_owner_under_the_shared_course_entry_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """Two learners on same-titled courses showed one bare title each, with
    nothing to tell the shared course from the organisation's own."""
    organisation, own, shared = _shared_and_own_course_world()
    on_shared = LearnerFactory(
        user=UserFactory(first_name="Shared", last_name="Learner"),
        organisation=organisation,
    )
    on_own = LearnerFactory(
        user=UserFactory(first_name="Own", last_name="Learner"),
        organisation=organisation,
    )
    LearnerCourseRegistrationFactory(learner=on_shared, course=shared)
    LearnerCourseRegistrationFactory(learner=on_own, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "learners"))

    rows = _shared_by_notes_by_row(document)
    assert _notes_for(rows, "Shared Learner") == ["Shared by Northwind Logistics"]
    assert _notes_for(rows, "Own Learner") == []


@pytest.mark.django_db
def test_cohorts_list_names_the_owner_under_the_shared_course_only(
    mock_site_context: Site, logged_in_client: Callable[[User], Client]
):
    """The Courses column of the cohorts list gave a shared course and an own
    course of one title the same bare text."""
    organisation, own, shared = _shared_and_own_course_world()
    on_shared = CohortFactory(organisation=organisation, name="Shared cohort")
    on_own = CohortFactory(organisation=organisation, name="Own cohort")
    CohortCourseRegistrationFactory(cohort=on_shared, course=shared)
    CohortCourseRegistrationFactory(cohort=on_own, course=own)
    client = logged_in_client(organisation_admin_viewer(organisation))

    document = _get_document(client, _interface_url(organisation.slug, "cohorts"))

    rows = _shared_by_notes_by_row(document)
    assert _notes_for(rows, "Shared cohort") == ["Shared by Northwind Logistics"]
    assert _notes_for(rows, "Own cohort") == []
