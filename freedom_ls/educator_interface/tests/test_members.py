"""RoleEntry and member_role_entries: what a member row says about the roles held."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.contrib.sites.models import Site
from django.db.models import Prefetch
from django.test import Client
from django.urls import reverse

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.audit_log.factories import AuditLogEntryFactory
from freedom_ls.educator_interface.members import (
    RoleEntry,
    describe_role_change,
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
class TestDescribeRoleChange:
    def test_shows_the_role_display_name_and_the_scope(
        self, mock_site_context: Site
    ) -> None:
        entry = AuditLogEntryFactory(
            action="role.granted",
            details={"role": "cohort_admin", "scope": "Cohort A"},
        )

        assert describe_role_change(entry) == "Cohort admin on Cohort A"

    def test_falls_back_to_the_code_for_a_role_no_longer_configured(
        self, mock_site_context: Site
    ) -> None:
        entry = AuditLogEntryFactory(
            action="role.removed",
            details={"role": "retired_role", "scope": "Cohort A"},
        )

        assert describe_role_change(entry) == "retired_role on Cohort A"


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
                "path_string": "members/__actions/remove_role",
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
