"""RoleEntry and staff_role_entries: what a member row says about the roles held."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import lxml.html
import pytest
import time_machine

from django.contrib.sites.models import Site
from django.db.models import Prefetch
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.staff import (
    RoleEntry,
    staff_role_entries,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    delete_cohort_leaving_role_rows,
)
from freedom_ls.learner_management.models import Cohort, StaffMember
from freedom_ls.learner_management.queries import staff_assignments
from freedom_ls.learner_management.role_assignment import (
    assign_role,
    set_staff_member_active,
)
from freedom_ls.learner_management.utils import ensure_staff_member
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse


def _entry(role: str, *cohorts: Cohort) -> RoleEntry:
    return RoleEntry(
        role=role,
        display_name=role,
        cohorts=cohorts,
        assigned_by=None,
        assigned_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _cohorts(organisation: Organisation, *names: str) -> list[Cohort]:
    return [CohortFactory(organisation=organisation, name=name) for name in names]


def _loaded(user: User, organisation: Organisation) -> User:
    """`user` as the members table loads it, with held_assignments prefetched."""
    loaded: User = User.objects.prefetch_related(
        Prefetch(
            "object_role_assignments",
            queryset=staff_assignments(organisation)
            .select_related("assigned_by")
            .prefetch_related("target"),
            to_attr="held_assignments",
        )
    ).get(pk=user.pk)
    return loaded


@pytest.mark.django_db
class TestRoleEntryScope:
    def test_an_organisation_role_reads_whole_organisation(
        self, mock_site_context: Site
    ) -> None:
        assert _entry("organisation_admin").scope == "Whole organisation"

    @pytest.mark.parametrize(
        "role", ["organisation_staff_viewer", "organisation_staff_roles_viewer"]
    )
    def test_a_viewer_role_targets_the_organisation_and_reads_whole_organisation(
        self, mock_site_context: Site, role: str
    ) -> None:
        entry = _entry(role)

        assert entry.target == "organisation"
        assert entry.scope == "Whole organisation"

    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            (["Alpha"], "Alpha"),
            (["Alpha", "Bravo"], "Alpha, Bravo"),
            (["Alpha", "Bravo", "Charlie", "Delta"], "Alpha, Bravo +2 more"),
        ],
    )
    def test_a_cohort_role_names_the_first_two_cohorts(
        self, mock_site_context: Site, names: list[str], expected: str
    ) -> None:
        cohorts = _cohorts(OrganisationFactory(), *names)

        assert _entry("cohort_admin", *cohorts).scope == expected

    def test_an_inactive_cohort_is_marked(self, mock_site_context: Site) -> None:
        cohort = CohortFactory(name="Alpha", is_active=False)

        assert _entry("cohort_viewer", cohort).scope == "Alpha (inactive)"

    def test_the_full_scope_names_every_cohort(self, mock_site_context: Site) -> None:
        cohorts = _cohorts(OrganisationFactory(), "Alpha", "Bravo", "Charlie")

        assert _entry("cohort_admin", *cohorts).full_scope == "Alpha, Bravo, Charlie"

    def test_the_full_scope_marks_an_inactive_cohort(
        self, mock_site_context: Site
    ) -> None:
        """The quick view lists full_scope, and it left "(inactive)" off an
        inactive cohort's name."""
        organisation = OrganisationFactory()
        active = CohortFactory(organisation=organisation, name="Alpha")
        inactive = CohortFactory(organisation=organisation, name="Old", is_active=False)

        assert (
            _entry("cohort_viewer", active, inactive).full_scope
            == "Alpha, Old (inactive)"
        )


@pytest.mark.django_db
class TestMemberRoleEntries:
    def test_entries_follow_the_order_of_the_staff_roles(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        grantor = UserFactory(superuser=True)
        user = UserFactory()
        assign_role(grantor, user, "cohort_viewer", cohort)
        assign_role(grantor, user, "organisation_admin", organisation)

        entries = staff_role_entries(_loaded(user, organisation), mock_site_context)

        assert [e.role for e in entries] == ["organisation_admin", "cohort_viewer"]

    def test_an_organisation_assignment_of_a_viewer_role_becomes_an_entry(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        user = UserFactory()
        assign_role(
            UserFactory(superuser=True),
            user,
            "organisation_staff_roles_viewer",
            organisation,
        )

        (entry,) = staff_role_entries(_loaded(user, organisation), mock_site_context)

        assert (entry.role, entry.target, entry.cohorts) == (
            "organisation_staff_roles_viewer",
            "organisation",
            (),
        )

    def test_the_display_name_comes_from_the_role_config(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        user = UserFactory()
        assign_role(
            UserFactory(superuser=True), user, "organisation_admin", organisation
        )

        (entry,) = staff_role_entries(_loaded(user, organisation), mock_site_context)

        assert entry.display_name == "Organisation admin"

    def test_cohorts_sort_by_name(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        zulu, alpha = _cohorts(organisation, "Zulu", "Alpha")
        grantor = UserFactory(superuser=True)
        user = UserFactory()
        assign_role(grantor, user, "cohort_admin", zulu)
        assign_role(grantor, user, "cohort_admin", alpha)

        (entry,) = staff_role_entries(_loaded(user, organisation), mock_site_context)

        assert [c.name for c in entry.cohorts] == ["Alpha", "Zulu"]

    def test_the_entry_names_the_grantor_of_the_newest_grant(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        first_cohort, second_cohort = _cohorts(organisation, "Alpha", "Bravo")
        older, newer = UserFactory(superuser=True), UserFactory(superuser=True)
        user = UserFactory()
        with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
            assign_role(older, user, "cohort_admin", first_cohort)
        with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
            assign_role(newer, user, "cohort_admin", second_cohort)

        (entry,) = staff_role_entries(_loaded(user, organisation), mock_site_context)

        assert entry.assigned_by == newer
        assert entry.assigned_at == datetime(2026, 2, 1, tzinfo=UTC)

    def test_a_cohort_assignment_with_no_target_raises(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        user = UserFactory()
        assign_role(UserFactory(superuser=True), user, "cohort_admin", cohort)
        delete_cohort_leaving_role_rows(cohort)
        loaded = User.objects.prefetch_related(
            Prefetch(
                "object_role_assignments",
                queryset=user.object_role_assignments.model.objects.prefetch_related(
                    "target"
                ),
                to_attr="held_assignments",
            )
        ).get(pk=user.pk)

        with pytest.raises(ValueError, match="no longer exists"):
            staff_role_entries(loaded, mock_site_context)


@pytest.mark.django_db
def test_the_organisation_log_shows_a_role_removed_through_the_action(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    cohort = CohortFactory(organisation=organisation, name="Cohort A")
    user = UserFactory()
    assign_role(UserFactory(superuser=True), user, "cohort_admin", cohort)

    staff_client.post(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": "staff/__actions/deactivate_role",
            },
        ),
        {"user": str(user.pk), "role": "cohort_admin"},
        HTTP_HX_REQUEST="true",
    )
    response = staff_client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": "audit-log",
            },
        )
    )

    assert "Cohort admin on Cohort A" in response.content.decode()


def _staff_page(
    client: Client, organisation: Organisation, query: str = ""
) -> lxml.html.HtmlElement:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "staff"},
        )
        + query
    )
    return lxml.html.fromstring(response.content.decode())


@pytest.mark.django_db
def test_the_members_table_and_its_scroll_region_are_named_members(
    staff_client: Client,
) -> None:
    """The caption and region name follow the page, not the User model."""
    organisation = OrganisationFactory()
    assign_role(
        UserFactory(superuser=True), UserFactory(), "organisation_admin", organisation
    )

    document = _staff_page(staff_client, organisation)

    (caption,) = document.cssselect("[data-table-region] table caption")
    (region,) = document.cssselect("[data-table-region] [role='region']")
    assert caption.text_content().strip() == "Staff members"
    assert region.get("aria-label") == "Staff members"


@pytest.mark.django_db
def test_a_member_rows_deactivate_trigger_names_the_member(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    member = UserFactory(first_name="Thandi", last_name="Nkosi")
    assign_role(UserFactory(superuser=True), member, "organisation_admin", organisation)

    document = _staff_page(staff_client, organisation)

    (button,) = [
        button
        for button in document.cssselect("td button[hx-get]")
        if f"deactivate?user={member.pk}" in button.get("hx-get")
    ]
    assert button.get("aria-label") == "Deactivate Thandi Nkosi"
    assert button.text_content().strip() == "Deactivate staff member"
    # It sits in the last column, which holds the buttons for the whole person.
    cell = button.xpath("ancestor::td")[0]
    assert cell.getnext() is None
    headers = [th.text_content().strip() for th in document.cssselect("thead th")]
    assert headers[-3:] == ["Roles", "Role actions", "Staff member actions"]


@pytest.mark.django_db
def test_a_staff_member_with_no_roles_says_so_and_offers_deactivate(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    member = UserFactory(first_name="Thandi", last_name="Nkosi")
    ensure_staff_member(member, organisation)

    document = _staff_page(staff_client, organisation)

    (cell,) = [
        cell
        for cell in document.cssselect("tbody td")
        if "No roles yet" in cell.text_content()
    ]
    assert not cell.cssselect("li")
    row = cell.xpath("ancestor::tr")[0]
    (button,) = [
        button
        for button in row.cssselect("td:last-child button[hx-get]")
        if button.text_content().strip() == "Deactivate staff member"
    ]
    assert f"deactivate?user={member.pk}" in button.get("hx-get")


def _staff_quick_view(
    client: Client, organisation: Organisation, user: User
) -> _MonkeyPatchedWSGIResponse:
    return client.get(
        reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": organisation.slug,
                "path_string": f"staff/{user.pk}/__quick-view",
            },
        ),
        HTTP_HX_REQUEST="true",
    )


@pytest.mark.django_db
def test_the_staff_quick_view_says_when_and_by_whom_each_role_was_added(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    member = UserFactory()
    grantor = UserFactory(superuser=True, first_name="Ada", last_name="Admin")
    with time_machine.travel(datetime(2026, 11, 3, 7, 37, tzinfo=UTC), tick=False):
        assign_role(grantor, member, "organisation_admin", organisation)

    response = _staff_quick_view(staff_client, organisation, member)
    table = _staff_page(staff_client, organisation)

    text = " ".join(response.content.decode().split())
    assert response.status_code == 200
    assert 'Added <time datetime="2026-11-03">3 Nov 2026</time> by Ada Admin' in text
    assert (
        "Added 3 Nov 2026"
        not in table.cssselect("[data-table-region]")[0].text_content()
    )


@pytest.mark.django_db
def test_the_staff_quick_view_of_an_account_with_no_name_has_no_subtitle(
    staff_client: Client,
) -> None:
    """An account with no name had its email as both the heading and the subtitle."""
    organisation = OrganisationFactory()
    member = UserFactory(first_name="", last_name="", email="nameless.member@qa.test")
    assign_role(UserFactory(superuser=True), member, "organisation_admin", organisation)

    content = _staff_quick_view(staff_client, organisation, member).content.decode()

    assert 'data-quick-view-title="nameless.member@qa.test"' in content
    assert 'data-quick-view-subtitle=""' in content


@pytest.mark.django_db
def test_each_staff_row_opens_its_quick_view(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    member = UserFactory()
    assign_role(UserFactory(superuser=True), member, "organisation_admin", organisation)

    document = _staff_page(staff_client, organisation)

    assert document.cssselect(f"[hx-get$='/staff/{member.pk}/__quick-view']")


@pytest.mark.django_db
def test_the_staff_quick_view_is_a_404_for_someone_not_on_the_staff(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    assign_role(
        UserFactory(superuser=True), UserFactory(), "organisation_admin", organisation
    )

    response = _staff_quick_view(staff_client, organisation, UserFactory())

    assert response.status_code == 404


@pytest.mark.django_db
class TestMembersEmptyState:
    def test_an_organisation_with_no_members_says_so(
        self, staff_client: Client
    ) -> None:
        document = _staff_page(staff_client, OrganisationFactory())

        message = document.cssselect("[data-table-region] table tbody td p")[0]
        assert message.text_content().strip() == (
            "No staff yet. Add the first staff member to give someone access to this "
            "organisation."
        )

    def test_the_add_member_action_is_offered_to_an_admin(
        self, staff_client: Client
    ) -> None:
        document = _staff_page(staff_client, OrganisationFactory())

        assert (
            "Add staff member"
            in document.cssselect("[data-table-region] table tbody td")[
                0
            ].text_content()
        )

    def test_the_add_member_action_is_not_offered_to_a_cohort_viewer(
        self, mock_site_context: Site, logged_in_client
    ) -> None:
        organisation = OrganisationFactory()
        viewer = UserFactory()
        assign_role(
            UserFactory(superuser=True),
            viewer,
            "cohort_viewer",
            CohortFactory(organisation=organisation),
        )

        response = logged_in_client(viewer).get(
            reverse(
                "educator_interface:interface",
                kwargs={
                    "organisation_slug": organisation.slug,
                    "path_string": "staff",
                },
            )
        )

        assert "Add staff member" not in response.content.decode()

    def test_a_search_with_no_match_says_nothing_matched(
        self, staff_client: Client
    ) -> None:
        document = _staff_page(staff_client, OrganisationFactory(), "?staff-q=zzz")

        message = document.cssselect("[data-table-region] table tbody td p")[0]
        assert message.text_content().strip() == "No staff members match these filters."

    def test_clear_filters_drops_the_search_and_filters(
        self, staff_client: Client
    ) -> None:
        document = _staff_page(
            staff_client,
            OrganisationFactory(),
            "?staff-q=zzz&staff-role=organisation_admin",
        )

        (link,) = [
            a
            for a in document.cssselect("[data-table-region] table tbody td a")
            if a.text_content().strip() == "Clear filters"
        ]
        href = link.get("href")
        assert "staff-q" not in href
        assert "members-role" not in href


@pytest.mark.django_db
def test_row_action_buttons_are_small_and_sit_in_an_actions_wrapper(
    staff_client: Client,
) -> None:
    """A button in a table cell takes the small size inside the actions
    wrapper, so two of them never touch."""
    organisation = OrganisationFactory()
    other = UserFactory(email="other@example.com")
    assign_role(UserFactory(superuser=True), other, "organisation_admin", organisation)

    document = _staff_page(staff_client, organisation)

    buttons = document.cssselect("td .btn")
    assert buttons
    assert all("btn-sm" in button.get("class").split() for button in buttons)
    assert all(
        "gap-2" in button.getparent().get("class", "").split() for button in buttons
    )


def _row_triggers(document: lxml.html.HtmlElement, user: User) -> list[str]:
    """The labels of the row-level triggers for `user`, in page order. Role
    entries' own buttons carry a `role=` parameter and are left out."""
    return [
        button.text_content().strip()
        for button in document.cssselect("td button[hx-get]")
        if f"user={user.pk}" in button.get("hx-get")
        and "role=" not in button.get("hx-get")
    ]


def _role_triggers(document: lxml.html.HtmlElement, user: User) -> list[str]:
    """The labels of the buttons on `user`'s role entries, in page order."""
    return [
        button.text_content().strip()
        for button in document.cssselect("td button[hx-get]")
        if f"user={user.pk}" in button.get("hx-get") and "role=" in button.get("hx-get")
    ]


@pytest.mark.django_db
def test_a_cohort_admin_gets_role_buttons_only_on_roles_held_on_their_cohorts(
    mock_site_context, logged_in_client
) -> None:
    organisation = OrganisationFactory()
    own = CohortFactory(organisation=organisation)
    foreign = CohortFactory(organisation=organisation)
    grantor = UserFactory(superuser=True)
    viewer = UserFactory(staff=True)
    assign_role(grantor, viewer, "cohort_admin", own)
    assign_role(grantor, viewer, "organisation_staff_roles_viewer", organisation)
    near = UserFactory()
    assign_role(grantor, near, "cohort_viewer", own)
    assign_role(grantor, near, "cohort_viewer", foreign)
    far = UserFactory()
    assign_role(grantor, far, "cohort_viewer", foreign)

    document = _staff_page(logged_in_client(viewer), organisation)

    assert (_role_triggers(document, near), _role_triggers(document, far)) == (
        ["Deactivate role", "Change cohorts"],
        [],
    )


@pytest.mark.django_db
def test_add_role_is_the_first_row_trigger(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    member = UserFactory()
    assign_role(UserFactory(superuser=True), member, "organisation_admin", organisation)

    document = _staff_page(staff_client, organisation)

    assert _row_triggers(document, member) == ["Add role", "Deactivate staff member"]


@pytest.mark.django_db
def test_an_inactive_staff_members_row_offers_add_role(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    member = UserFactory()
    assign_role(UserFactory(superuser=True), member, "organisation_admin", organisation)
    assign_role(
        UserFactory(superuser=True), UserFactory(), "organisation_admin", organisation
    )
    set_staff_member_active(
        UserFactory(superuser=True),
        StaffMember.objects.get(user=member, organisation=organisation),
        False,
    )

    document = _staff_page(staff_client, organisation)

    assert _row_triggers(document, member) == ["Add role", "Reactivate staff member"]


@pytest.mark.django_db
def test_a_site_level_admins_row_offers_add_role_and_no_state_trigger(
    staff_client: Client,
) -> None:
    organisation = OrganisationFactory()
    site_admin = UserFactory()
    assign_role(
        UserFactory(superuser=True), site_admin, "site_admin", organisation.site
    )
    ensure_staff_member(site_admin, organisation)

    document = _staff_page(staff_client, organisation)

    assert _row_triggers(document, site_admin) == ["Add role"]


def _two_role_member(organisation: Organisation) -> User:
    member = cast(User, UserFactory(first_name="Oscar", last_name="Owner"))
    grantor = UserFactory(superuser=True)
    assign_role(grantor, member, "organisation_admin", organisation)
    assign_role(
        grantor, member, "cohort_viewer", CohortFactory(organisation=organisation)
    )
    return member


@pytest.mark.django_db
def test_a_staff_card_puts_each_roles_buttons_under_that_role(
    staff_client: Client,
) -> None:
    """A card has no Role actions section: a person with two roles shows
    which Deactivate role belongs to which role."""
    organisation = OrganisationFactory()
    member = _two_role_member(organisation)

    document = _staff_page(staff_client, organisation)

    (card,) = [
        card
        for card in document.cssselect("li.panel-data-table-card")
        if f"user={member.pk}" in lxml.html.tostring(card).decode()
    ]
    assert "Role actions" not in card.text_content()
    blocks = {
        item.cssselect("span")[0].text_content().strip(): [
            button.text_content().strip() for button in item.cssselect("button[hx-get]")
        ]
        for item in card.cssselect("ul[aria-label='Roles'] > li")
    }
    assert blocks == {
        "Organisation admin": ["Deactivate role"],
        "Cohort viewer": ["Deactivate role", "Change cohorts"],
    }


@pytest.mark.django_db
def test_every_role_button_names_its_role_and_person(staff_client: Client) -> None:
    organisation = OrganisationFactory()
    member = _two_role_member(organisation)

    document = _staff_page(staff_client, organisation)

    labels = {
        button.get("aria-label")
        for button in document.cssselect("button[hx-get]")
        if f"user={member.pk}&role=" in button.get("hx-get")
    }
    assert labels == {
        "Deactivate Organisation admin for Oscar Owner",
        "Deactivate Cohort viewer for Oscar Owner",
        "Change Cohort viewer cohorts for Oscar Owner",
    }
