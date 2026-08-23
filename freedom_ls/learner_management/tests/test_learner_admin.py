"""Tests for LearnerAdmin and the CohortMembershipInline learner narrowing."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib import admin
from django.db.models import QuerySet
from django.forms import ModelChoiceField
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse
from django.urls.resolvers import ResolverMatch

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.admin import CohortMembershipInline, LearnerAdmin
from freedom_ls.learner_management.factories import CohortFactory, LearnerFactory
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.factories import OrganisationFactory

ADD_URL_NAME = "admin:freedom_ls_learner_management_learner_add"


def _request_for_cohort(cohort: Cohort | None) -> HttpRequest:
    """An admin request whose resolver match names ``cohort``, or none of them
    -- the add page, which carries no object_id."""
    request = RequestFactory().get("/")
    request.resolver_match = ResolverMatch(
        func=lambda *args, **kwargs: None,
        args=(),
        kwargs={} if cohort is None else {"object_id": str(cohort.pk)},
    )
    return request


def _learner_choices(request: HttpRequest) -> QuerySet[Learner]:
    """The learners the inline's learner dropdown offers on ``request``."""
    inline = CohortMembershipInline(Cohort, admin.site)
    field = cast(
        "ModelChoiceField[Learner]",
        inline.formfield_for_foreignkey(
            CohortMembership._meta.get_field("learner"), request
        ),
    )
    return cast("QuerySet[Learner]", field.queryset)


@pytest.fixture
def admin_instance() -> LearnerAdmin:
    return LearnerAdmin(Learner, admin.site)


@pytest.fixture
def staff_client(mock_site_context, logged_in_client):
    """The Django admin as a superuser -- these admin classes carry no
    role-based narrowing of their own."""
    return logged_in_client(UserFactory(superuser=True))


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
    """Covers formfield_for_foreignkey's queryset only. The inline declares
    `learner` in autocomplete_fields, so the options a person actually sees are
    served by AutocompleteJsonView from LearnerAdmin.get_search_results, which
    never receives this queryset -- these tests passing is not evidence that
    the rendered dropdown is scoped. See QA bug B1.
    """

    def test_offers_only_learners_from_the_cohorts_organisation(
        self, mock_site_context
    ) -> None:
        own_organisation = OrganisationFactory()
        other_organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=own_organisation, name="Cohort A")
        own_learner = LearnerFactory(organisation=own_organisation)
        LearnerFactory(organisation=other_organisation)

        choices = _learner_choices(_request_for_cohort(cohort))

        assert list(choices) == [own_learner]

    def test_offers_every_learner_when_adding_a_brand_new_cohort(
        self, mock_site_context
    ) -> None:
        """No `object_id` on the add page, so the queryset is left at its default."""
        learner = LearnerFactory(organisation=OrganisationFactory())

        choices = _learner_choices(_request_for_cohort(None))

        assert learner in choices
