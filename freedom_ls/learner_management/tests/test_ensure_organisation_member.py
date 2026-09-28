"""Tests for ensure_organisation_member, the get-or-create gate helper.

Unlike ensure_learner, this never reactivates an existing row: a deactivated
member must stay deactivated until someone explicitly reactivates them.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.learner_management.models import OrganisationMember
from freedom_ls.learner_management.utils import ensure_organisation_member
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
class TestEnsureOrganisationMember:
    """Arranged with OrganisationMember.objects.create, not
    OrganisationMemberFactory: the factory is a thin wrapper over the model,
    but building starting state through the function under test would still
    test it against itself, so a raw create keeps the arrangement independent."""

    def test_creates_a_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        member = ensure_organisation_member(user, organisation)

        assert member.pk is not None
        assert member.user == user
        assert member.organisation == organisation
        assert member.is_active is True

    def test_returns_an_existing_active_row_unchanged(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        existing = OrganisationMember.objects.create(
            user=user, organisation=organisation, is_active=True
        )

        returned = ensure_organisation_member(user, organisation)

        assert returned.pk == existing.pk
        assert (
            OrganisationMember.objects.filter(
                user=user, organisation=organisation
            ).count()
            == 1
        )

    def test_returns_an_inactive_row_still_inactive(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        existing = OrganisationMember.objects.create(
            user=user, organisation=organisation, is_active=False
        )

        returned = ensure_organisation_member(user, organisation)

        assert returned.pk == existing.pk
        assert returned.is_active is False

    def test_finds_the_existing_row_when_a_different_site_is_ambient(
        self, mock_site_context
    ):
        """Mirrors ensure_learner's own version of this test: the lookup must
        use _base_manager, or an ambient site foreign to the organisation
        being handled makes get_or_create miss the row below and attempt a
        second INSERT, raising IntegrityError on
        unique_member_per_organisation."""
        user = UserFactory()
        organisation = OrganisationFactory(site=SiteFactory())

        ensure_organisation_member(user, organisation)
        ensure_organisation_member(user, organisation)

        assert (
            OrganisationMember._base_manager.filter(
                user=user, organisation=organisation
            ).count()
            == 1
        )
