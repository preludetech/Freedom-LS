"""Tests for ensure_learner, the idempotent get-or-reactivate helper."""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import SiteFactory, UserFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.utils import ensure_learner
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
class TestEnsureLearner:
    """Arranged with Learner.objects.create, not LearnerFactory: the factory
    delegates to ensure_learner, so building the starting state with it would
    test the function against itself."""

    def test_calling_twice_creates_one_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        ensure_learner(user, organisation)
        ensure_learner(user, organisation)

        assert Learner.objects.filter(user=user, organisation=organisation).count() == 1

    def test_calling_twice_returns_the_same_row(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()

        first = ensure_learner(user, organisation)
        second = ensure_learner(user, organisation)

        assert first.pk == second.pk

    def test_reactivates_a_removed_learner(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        learner = Learner.objects.create(
            user=user, organisation=organisation, is_active=False
        )

        ensure_learner(user, organisation)

        learner.refresh_from_db()
        assert learner.is_active is True

    def test_finds_the_existing_row_when_a_different_site_is_ambient(
        self, mock_site_context
    ):
        """The organisation being handled is not always the site the current
        request is for. Using the site-aware manager for the lookup half of
        update_or_create would AND the ambient site onto the query, miss the
        row created below, and attempt a second INSERT — raising
        IntegrityError on unique_learner_per_organisation. A test that only
        calls ensure_learner once passes against that broken version too."""
        user = UserFactory()
        organisation = OrganisationFactory(site=SiteFactory())

        ensure_learner(user, organisation)
        ensure_learner(user, organisation)

        assert (
            Learner._base_manager.filter(user=user, organisation=organisation).count()
            == 1
        )
