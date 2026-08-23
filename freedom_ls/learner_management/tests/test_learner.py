"""Tests for the Learner model."""

from __future__ import annotations

import pytest

from django.db import IntegrityError

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.organisations.factories import OrganisationFactory


@pytest.mark.django_db
class TestLearnerUniqueness:
    def test_duplicate_user_and_organisation_is_rejected(self, mock_site_context):
        user = UserFactory()
        organisation = OrganisationFactory()
        Learner.objects.create(user=user, organisation=organisation)

        with pytest.raises(IntegrityError):
            Learner.objects.create(user=user, organisation=organisation)

    def test_same_user_may_hold_rows_in_two_organisations(self, mock_site_context):
        user = UserFactory()
        Learner.objects.create(user=user, organisation=OrganisationFactory())
        Learner.objects.create(user=user, organisation=OrganisationFactory())

        assert Learner.objects.filter(user=user).count() == 2


@pytest.mark.django_db
class TestLearnerSite:
    def test_learner_takes_its_site_from_its_organisation(self, mock_site_context):
        organisation = OrganisationFactory()

        learner = Learner.objects.create(user=UserFactory(), organisation=organisation)

        assert learner.site_id == organisation.site_id
