"""Tests for LearnerAdmin and the CohortMembershipInline learner narrowing."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.test import Client, RequestFactory
from django.urls import reverse
from django.urls.resolvers import ResolverMatch

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.admin import CohortMembershipInline, LearnerAdmin
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.factories import OrganisationFactory

ADD_URL_NAME = "admin:freedom_ls_learner_management_learner_add"


@pytest.fixture
def admin_instance() -> LearnerAdmin:
    return LearnerAdmin(Learner, admin.site)


@pytest.fixture
def staff_client(mock_site_context, db):
    user = UserFactory(superuser=True)
    client = Client()
    client.force_login(user)
    return client


class TestDeletePermission:
    def test_delete_permission_is_always_false(
        self, admin_instance: LearnerAdmin
    ) -> None:
        assert admin_instance.has_delete_permission(request=None) is False


@pytest.mark.django_db
class TestLearnerAdminSave:
    def test_creating_learner_via_admin_takes_its_site_from_the_organisation(
        self, staff_client
    ) -> None:
        user = UserFactory()
        organisation = OrganisationFactory()
        url = reverse(ADD_URL_NAME)

        response = staff_client.post(
            url,
            {"user": user.pk, "organisation": organisation.pk, "is_active": "on"},
        )

        assert response.status_code == 302
        learner = Learner.objects.get(user=user, organisation=organisation)
        assert learner.site_id == organisation.site_id


@pytest.mark.django_db
class TestCohortMembershipInlineLearnerField:
    def test_offers_only_learners_from_the_cohorts_organisation(
        self, mock_site_context
    ) -> None:
        own_organisation = OrganisationFactory()
        other_organisation = OrganisationFactory()
        cohort = Cohort.objects.create(organisation=own_organisation, name="Cohort A")
        own_learner = Learner.objects.create(
            user=UserFactory(), organisation=own_organisation
        )
        other_learner = Learner.objects.create(
            user=UserFactory(), organisation=other_organisation
        )

        request = RequestFactory().get("/")
        request.resolver_match = ResolverMatch(
            func=lambda *args, **kwargs: None,
            args=(),
            kwargs={"object_id": str(cohort.pk)},
        )

        inline = CohortMembershipInline(Cohort, admin.site)
        field = inline.formfield_for_foreignkey(
            CohortMembership._meta.get_field("learner"), request
        )

        assert field is not None
        assert field.queryset is not None
        queryset = field.queryset
        assert own_learner in queryset
        assert other_learner not in queryset

    def test_offers_every_learner_when_adding_a_brand_new_cohort(
        self, mock_site_context
    ) -> None:
        """No `object_id` on the add page, so the queryset is left at its default."""
        organisation = OrganisationFactory()
        learner = Learner.objects.create(user=UserFactory(), organisation=organisation)

        request = RequestFactory().get("/")
        request.resolver_match = ResolverMatch(
            func=lambda *args, **kwargs: None, args=(), kwargs={}
        )

        inline = CohortMembershipInline(Cohort, admin.site)
        field = inline.formfield_for_foreignkey(
            CohortMembership._meta.get_field("learner"), request
        )

        assert field is not None
        assert field.queryset is not None
        assert learner in field.queryset
