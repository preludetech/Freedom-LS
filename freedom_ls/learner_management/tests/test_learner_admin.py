"""Tests for LearnerAdmin and the CohortMembershipInline learner narrowing."""

from __future__ import annotations

import warnings
from typing import cast
from urllib.parse import parse_qsl
from uuid import uuid4

import pytest

from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect
from django.core.paginator import UnorderedObjectListWarning
from django.db.models import Model, QuerySet
from django.forms import ModelChoiceField
from django.http import HttpRequest
from django.test import RequestFactory
from django.urls import reverse
from django.urls.resolvers import ResolverMatch

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.learner_management.admin import (
    SCOPE_TO_MEMBERS_OF_COHORT,
    SCOPE_TO_ORGANISATION_OF_COHORT,
    CohortMembershipInline,
    LearnerAdmin,
    UserCohortDeadlineOverrideInline,
)
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
    UserCohortDeadlineOverride,
)
from freedom_ls.organisations.factories import OrganisationFactory

ADD_URL_NAME = "admin:freedom_ls_learner_management_learner_add"
AUTOCOMPLETE_URL_NAME = "admin:autocomplete"
COHORT_CHANGE_URL_NAME = "admin:freedom_ls_learner_management_cohort_change"
LEARNER_CHANGELIST_URL_NAME = "admin:freedom_ls_learner_management_learner_changelist"
REGISTRATION_CHANGE_URL_NAME = (
    "admin:freedom_ls_learner_management_cohortcourseregistration_change"
)


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


def _request_for_cohort_course_registration(
    registration: CohortCourseRegistration,
) -> HttpRequest:
    """An admin request whose resolver match names ``registration``."""
    request = RequestFactory().get("/")
    request.resolver_match = ResolverMatch(
        func=lambda *args, **kwargs: None,
        args=(),
        kwargs={"object_id": str(registration.pk)},
    )
    return request


def _learner_field(request: HttpRequest) -> ModelChoiceField[Learner]:
    """The inline's learner form field as built on ``request``."""
    inline = CohortMembershipInline(Cohort, admin.site)
    return cast(
        "ModelChoiceField[Learner]",
        inline.formfield_for_foreignkey(
            CohortMembership._meta.get_field("learner"), request
        ),
    )


def _learner_choices(request: HttpRequest) -> QuerySet[Learner]:
    """The learners the inline's learner dropdown validates against."""
    return cast("QuerySet[Learner]", _learner_field(request).queryset)


def _autocomplete_request(
    field: ModelChoiceField[Learner], model: type[Model], term: str = ""
) -> tuple[str, dict[str, str]]:
    """The URL and params the rendered dropdown for ``field`` actually fetches.

    The widget supplies the URL through data-ajax--url; admin/js/autocomplete.js
    appends the rest. Deriving them from the widget rather than hardcoding them
    is what keeps these tests honest -- a widget that stops naming its scope
    stops narrowing the results here too.
    """
    widget = cast("AutocompleteSelect", field.widget)
    url, _, query = widget.get_url().partition("?")
    params = dict(parse_qsl(query))
    params.update(
        {
            "term": term,
            "app_label": model._meta.app_label,
            "model_name": model._meta.model_name or "",
            "field_name": "learner",
        }
    )
    return url, params


def _offered_ids(staff_client, url: str, params: dict) -> set[str]:
    """The learner ids the autocomplete endpoint returns for ``params``."""
    response = staff_client.get(url, params)
    assert response.status_code == 200
    return {result["id"] for result in response.json()["results"]}


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
    """Covers formfield_for_foreignkey's queryset only -- what validates the
    learner that comes back. The options a person is actually offered come from
    the autocomplete endpoint; TestLearnerAutocompleteEndpoint covers those.
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


@pytest.mark.django_db
class TestLearnerAutocompleteEndpoint:
    """The options a person is actually offered.

    autocomplete_fields routes the dropdown through the shared
    admin:autocomplete endpoint, which builds its results from
    LearnerAdmin.get_search_results and never sees the inline's narrowed
    formfield queryset. These tests exercise that endpoint the way the browser
    does, so they -- not the queryset tests above -- are what proves the
    dropdown is scoped.
    """

    def test_a_cohorts_dropdown_omits_another_organisations_learner(
        self, staff_client
    ) -> None:
        own_organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=own_organisation, name="Cohort A")
        own_learner = LearnerFactory(organisation=own_organisation)
        foreign_learner = LearnerFactory(organisation=OrganisationFactory())
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )

        offered = _offered_ids(staff_client, url, params)

        assert str(own_learner.pk) in offered
        assert str(foreign_learner.pk) not in offered

    def test_it_still_offers_the_cohorts_own_removed_learner(
        self, staff_client
    ) -> None:
        """Removing a learner must not make the cohorts holding them unsavable
        -- see TestCohortChangePageWithARemovedLearner."""
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        removed = LearnerFactory(organisation=organisation, is_active=False)
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )

        assert str(removed.pk) in _offered_ids(staff_client, url, params)

    def test_the_add_page_dropdown_offers_every_learner(self, staff_client) -> None:
        """No cohort exists yet, so there is nothing to scope to. Picking wrong
        is caught by CohortMembership.clean() on save."""
        learners = [
            LearnerFactory(organisation=OrganisationFactory()) for _ in range(2)
        ]
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(None)), CohortMembership
        )

        offered = _offered_ids(staff_client, url, params)

        assert SCOPE_TO_ORGANISATION_OF_COHORT not in params
        assert {str(learner.pk) for learner in learners} <= offered

    def test_a_scope_that_is_not_a_uuid_offers_nothing(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        LearnerFactory(organisation=organisation)
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )
        params[SCOPE_TO_ORGANISATION_OF_COHORT] = "not-a-uuid"

        assert _offered_ids(staff_client, url, params) == set()

    def test_a_scope_naming_no_cohort_offers_nothing(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        LearnerFactory(organisation=organisation)
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )
        params[SCOPE_TO_ORGANISATION_OF_COHORT] = str(uuid4())

        assert _offered_ids(staff_client, url, params) == set()

    def test_an_unscoped_learner_dropdown_is_left_alone(self, staff_client) -> None:
        """LearnerCourseRegistration has no parent organisation to scope to, so
        its learner dropdown still offers every learner on the site. Guards
        against a fix that narrows the shared endpoint for everyone."""
        learners = [
            LearnerFactory(organisation=OrganisationFactory()) for _ in range(2)
        ]

        offered = _offered_ids(
            staff_client,
            reverse(AUTOCOMPLETE_URL_NAME),
            {
                "term": "",
                "app_label": LearnerCourseRegistration._meta.app_label,
                "model_name": LearnerCourseRegistration._meta.model_name or "",
                "field_name": "learner",
            },
        )

        assert {str(learner.pk) for learner in learners} <= offered


@pytest.mark.django_db
class TestLearnerOrdering:
    """The autocomplete endpoint paginates its results, so the queryset behind
    them has to have a stable order or page 2 can repeat or skip a learner."""

    def test_the_dropdown_offers_learners_in_a_stable_order(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        for email in ("zoe@ordering.test", "adam@ordering.test", "mia@ordering.test"):
            LearnerFactory(organisation=organisation, user=UserFactory(email=email))
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )

        response = staff_client.get(url, params)

        assert [result["text"] for result in response.json()["results"]] == [
            f"adam@ordering.test - {organisation.name}",
            f"mia@ordering.test - {organisation.name}",
            f"zoe@ordering.test - {organisation.name}",
        ]

    def test_paginating_the_dropdown_does_not_warn_about_an_unordered_queryset(
        self, staff_client
    ) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        LearnerFactory(organisation=organisation)
        url, params = _autocomplete_request(
            _learner_field(_request_for_cohort(cohort)), CohortMembership
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            staff_client.get(url, params)

        assert not [
            warning
            for warning in caught
            if issubclass(warning.category, UnorderedObjectListWarning)
        ]


@pytest.mark.django_db
class TestLearnerChangelistSearch:
    def test_searching_learners_is_unaffected_by_the_scoping(
        self, staff_client
    ) -> None:
        """get_search_results is shared with the changelist, which must keep
        seeing every learner on the site."""
        learners = [
            LearnerFactory(
                organisation=OrganisationFactory(),
                user=UserFactory(last_name="Scopetest"),
            )
            for _ in range(2)
        ]

        response = staff_client.get(
            reverse(LEARNER_CHANGELIST_URL_NAME), {"q": "Scopetest"}
        )

        assert set(response.context["cl"].queryset) == set(learners)


@pytest.mark.django_db
class TestCohortChangePageDropdown:
    def test_the_rendered_dropdown_url_names_the_cohorts_scope(
        self, staff_client
    ) -> None:
        """Proves the scoped widget survives the whole admin stack -- unfold's
        own formfield_for_foreignkey, RelatedFieldWidgetWrapper and unfold's
        wrapper template -- not just a direct call to the inline."""
        cohort = CohortFactory(organisation=OrganisationFactory(), name="Cohort A")

        response = staff_client.get(reverse(COHORT_CHANGE_URL_NAME, args=[cohort.pk]))

        assert (
            f"{SCOPE_TO_ORGANISATION_OF_COHORT}={cohort.pk}"
            in response.content.decode()
        )


def _override_learner_field(
    request: HttpRequest,
) -> ModelChoiceField[Learner]:
    """The deadline-override inline's learner form field on ``request``."""
    inline = UserCohortDeadlineOverrideInline(CohortCourseRegistration, admin.site)
    return cast(
        "ModelChoiceField[Learner]",
        inline.formfield_for_foreignkey(
            UserCohortDeadlineOverride._meta.get_field("learner"), request
        ),
    )


@pytest.mark.django_db
class TestDeadlineOverrideLearnerDropdown:
    """UserCohortDeadlineOverride.clean() requires the learner to be a member of
    the registration's cohort, so the dropdown offers exactly those."""

    def test_it_omits_a_learner_who_is_not_in_the_cohort(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        registration = CohortCourseRegistrationFactory(cohort=cohort)
        member = CohortMembershipFactory(cohort=cohort).learner
        non_member = LearnerFactory(organisation=organisation)
        url, params = _autocomplete_request(
            _override_learner_field(
                _request_for_cohort_course_registration(registration)
            ),
            UserCohortDeadlineOverride,
        )

        offered = _offered_ids(staff_client, url, params)

        assert str(member.pk) in offered
        assert str(non_member.pk) not in offered

    def test_the_rendered_dropdown_url_names_the_cohorts_scope(
        self, staff_client
    ) -> None:
        cohort = CohortFactory(organisation=OrganisationFactory(), name="Cohort A")
        registration = CohortCourseRegistrationFactory(cohort=cohort)

        response = staff_client.get(
            reverse(REGISTRATION_CHANGE_URL_NAME, args=[registration.pk])
        )

        assert f"{SCOPE_TO_MEMBERS_OF_COHORT}={cohort.pk}" in response.content.decode()

    def test_the_field_queryset_matches_what_the_dropdown_offers(
        self, mock_site_context
    ) -> None:
        """The widget scopes the options; this queryset is what validates the
        learner that comes back. They must agree."""
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        registration = CohortCourseRegistrationFactory(cohort=cohort)
        member = CohortMembershipFactory(cohort=cohort).learner
        LearnerFactory(organisation=organisation)

        field = _override_learner_field(
            _request_for_cohort_course_registration(registration)
        )

        assert list(field.queryset) == [member]


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


def _registration_change_payload(
    registration: CohortCourseRegistration, learner: Learner
) -> dict[str, str]:
    """The registration change form with one new deadline-override row for
    ``learner``."""
    return {
        "cohort": str(registration.cohort_id),
        "collection": str(registration.collection_id),
        "is_active": "on",
        "cohortdeadline_set-TOTAL_FORMS": "0",
        "cohortdeadline_set-INITIAL_FORMS": "0",
        "cohortdeadline_set-MIN_NUM_FORMS": "0",
        "cohortdeadline_set-MAX_NUM_FORMS": "1000",
        "deadline_overrides-TOTAL_FORMS": "1",
        "deadline_overrides-INITIAL_FORMS": "0",
        "deadline_overrides-MIN_NUM_FORMS": "0",
        "deadline_overrides-MAX_NUM_FORMS": "1000",
        "deadline_overrides-0-learner": str(learner.pk),
        "deadline_overrides-0-deadline_0": "2030-01-01",
        "deadline_overrides-0-deadline_1": "12:00:00",
        "deadline_overrides-0-is_hard_deadline": "on",
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


@pytest.mark.django_db
class TestDeadlineOverrideChangePageWithAnOutOfCohortLearner:
    """Narrowing the inline's queryset means an out-of-cohort learner now fails
    field validation, leaving cleaned_data without one. clean() must survive
    that and let the field error surface -- the crash QA bug B2 described."""

    def test_it_is_a_validation_error_not_a_crash(self, staff_client) -> None:
        organisation = OrganisationFactory()
        cohort = CohortFactory(organisation=organisation, name="Cohort A")
        registration = CohortCourseRegistrationFactory(cohort=cohort)
        non_member = LearnerFactory(organisation=organisation)

        response = staff_client.post(
            reverse(REGISTRATION_CHANGE_URL_NAME, args=[registration.pk]),
            _registration_change_payload(registration, non_member),
        )

        assert response.status_code == 200
        assert not UserCohortDeadlineOverride.objects.filter(
            learner=non_member
        ).exists()
