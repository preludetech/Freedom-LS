"""RoleEntry and member_role_entries: what a member row says about the roles held."""

from __future__ import annotations

from datetime import UTC, datetime

import lxml.html
import pytest
import time_machine

from django.contrib.sites.models import Site
from django.db.models import Prefetch
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.educator_interface.members import (
    RoleEntry,
    member_role_entries,
)
from freedom_ls.learner_management.factories import (
    CohortFactory,
    delete_cohort_leaving_role_rows,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import member_assignments
from freedom_ls.learner_management.role_assignment import assign_role
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.models import Organisation


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
            queryset=member_assignments(organisation)
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


@pytest.mark.django_db
class TestMemberRoleEntries:
    def test_entries_follow_the_order_of_the_member_roles(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation)
        grantor = UserFactory(superuser=True)
        user = UserFactory()
        assign_role(grantor, user, "cohort_viewer", cohort)
        assign_role(grantor, user, "organisation_admin", organisation)

        entries = member_role_entries(_loaded(user, organisation), mock_site_context)

        assert [e.role for e in entries] == ["organisation_admin", "cohort_viewer"]

    def test_the_display_name_comes_from_the_role_config(
        self, mock_site_context: Site
    ) -> None:
        organisation = OrganisationFactory()
        user = UserFactory()
        assign_role(
            UserFactory(superuser=True), user, "organisation_admin", organisation
        )

        (entry,) = member_role_entries(_loaded(user, organisation), mock_site_context)

        assert entry.display_name == "Organisation admin"

    def test_cohorts_sort_by_name(self, mock_site_context: Site) -> None:
        organisation = OrganisationFactory()
        zulu, alpha = _cohorts(organisation, "Zulu", "Alpha")
        grantor = UserFactory(superuser=True)
        user = UserFactory()
        assign_role(grantor, user, "cohort_admin", zulu)
        assign_role(grantor, user, "cohort_admin", alpha)

        (entry,) = member_role_entries(_loaded(user, organisation), mock_site_context)

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

        (entry,) = member_role_entries(_loaded(user, organisation), mock_site_context)

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
            member_role_entries(loaded, mock_site_context)


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
                "path_string": "members/__actions/deactivate_role",
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


def _members_page(
    client: Client, organisation: Organisation, query: str = ""
) -> lxml.html.HtmlElement:
    response = client.get(
        reverse(
            "educator_interface:interface",
            kwargs={"organisation_slug": organisation.slug, "path_string": "members"},
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

    document = _members_page(staff_client, organisation)

    (caption,) = document.cssselect("[data-table-region] table caption")
    (region,) = document.cssselect("[data-table-region] [role='region']")
    assert caption.text_content().strip() == "Members"
    assert region.get("aria-label") == "Members"


@pytest.mark.django_db
class TestMembersEmptyState:
    def test_an_organisation_with_no_members_says_so(
        self, staff_client: Client
    ) -> None:
        document = _members_page(staff_client, OrganisationFactory())

        message = document.cssselect("[data-table-region] table tbody td p")[0]
        assert message.text_content().strip() == (
            "No members yet. Add the first member to give someone access to this "
            "organisation."
        )

    def test_the_add_member_action_is_offered_to_an_admin(
        self, staff_client: Client
    ) -> None:
        document = _members_page(staff_client, OrganisationFactory())

        assert (
            "Add member"
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
                    "path_string": "members",
                },
            )
        )

        assert "Add member" not in response.content.decode()

    def test_a_search_with_no_match_says_nothing_matched(
        self, staff_client: Client
    ) -> None:
        document = _members_page(staff_client, OrganisationFactory(), "?members-q=zzz")

        message = document.cssselect("[data-table-region] table tbody td p")[0]
        assert message.text_content().strip() == "No members match these filters."

    def test_clear_filters_drops_the_search_and_filters(
        self, staff_client: Client
    ) -> None:
        document = _members_page(
            staff_client,
            OrganisationFactory(),
            "?members-q=zzz&members-role=organisation_admin",
        )

        (link,) = [
            a
            for a in document.cssselect("[data-table-region] table tbody td a")
            if a.text_content().strip() == "Clear filters"
        ]
        href = link.get("href")
        assert "members-q" not in href
        assert "members-role" not in href
