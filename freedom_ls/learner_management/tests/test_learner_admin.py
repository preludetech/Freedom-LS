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
from freedom_ls.learner_management.factories import (
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.organisations.factories import OrganisationFactory

ADD_URL_NAME = "admin:freedom_ls_learner_management_learner_add"
COHORT_CHANGE_URL_NAME = "admin:freedom_ls_learner_management_cohort_change"


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

    def test_offers_a_removed_learner_from_the_cohorts_organisation(
        self, mock_site_context
    ) -> None:
        """This queryset also validates the inline rows that already exist, so
        excluding removed learners would make a cohort holding one unsavable."""
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        removed = LearnerFactory(organisation=organisation, is_active=False)

        choices = _learner_choices(_request_for_cohort(cohort))

        assert removed in choices

    def test_offers_every_learner_when_adding_a_brand_new_cohort(
        self, mock_site_context
    ) -> None:
        """No `object_id` on the add page, so the queryset is left at its default."""
        learner = LearnerFactory(organisation=OrganisationFactory())

        choices = _learner_choices(_request_for_cohort(None))

        assert learner in choices


def _cohort_change_payload(
    cohort: Cohort, membership: CohortMembership
) -> dict[str, str]:
    """A minimal, unmodified round-trip of the cohort change form: the cohort's
    own fields plus the one membership inline row, resubmitted as-is."""
    return {
        "name": cohort.name,
        "organisation": str(cohort.organisation_id),
        "cohortmembership_set-TOTAL_FORMS": "1",
        "cohortmembership_set-INITIAL_FORMS": "1",
        "cohortmembership_set-MIN_NUM_FORMS": "0",
        "cohortmembership_set-MAX_NUM_FORMS": "1000",
        "cohortmembership_set-0-id": str(membership.pk),
        "cohortmembership_set-0-cohort": str(cohort.pk),
        "cohortmembership_set-0-learner": str(membership.learner_id),
        "course_registrations-TOTAL_FORMS": "0",
        "course_registrations-INITIAL_FORMS": "0",
        "course_registrations-MIN_NUM_FORMS": "0",
        "course_registrations-MAX_NUM_FORMS": "1000",
    }


@pytest.mark.django_db
class TestCohortChangePageWithARemovedLearner:
    """The admin is the only place a learner is removed, so it must not then
    refuse to save the cohorts that learner still belongs to."""

    def test_the_cohort_still_saves(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        removed = LearnerFactory(organisation=organisation, is_active=False)
        membership = CohortMembershipFactory(cohort=cohort, learner=removed)

        response = staff_client.post(
            reverse(COHORT_CHANGE_URL_NAME, args=[cohort.pk]),
            _cohort_change_payload(cohort, membership),
        )

        assert response.status_code == 302

    def test_an_edit_made_on_the_page_is_persisted(self, staff_client) -> None:
        """Renaming proves the form actually saved. Asserting the membership
        merely survived would pass on the rejected save too, since a rejected
        save deletes nothing."""
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        removed = LearnerFactory(organisation=organisation, is_active=False)
        membership = CohortMembershipFactory(cohort=cohort, learner=removed)
        payload = _cohort_change_payload(cohort, membership)
        payload["name"] = "Renamed Cohort"

        staff_client.post(reverse(COHORT_CHANGE_URL_NAME, args=[cohort.pk]), payload)

        cohort.refresh_from_db()
        assert cohort.name == "Renamed Cohort"
