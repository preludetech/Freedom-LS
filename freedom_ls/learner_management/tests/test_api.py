"""The registration endpoints, through a real key on the test client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.api"):
    pytest.skip("freedom_ls.api not installed", allow_module_level=True)

from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import bearer_auth_for, collect_pages
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.learner_actions import deactivate_registration
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.utils import deactivate_cohort_registration
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LEARNER_LIST_URL_NAME = "api:learner_course_registration_list"
LEARNER_DETAIL_URL_NAME = "api:learner_course_registration_detail"

LEARNER_EXPECTED_FIELDS = {
    "id",
    "course_id",
    "course_title",
    "user_id",
    "user_email",
    "user_first_name",
    "user_last_name",
    "organisation_id",
    "organisation_name",
    "self_registered",
    "is_active",
    "registered_at",
    "updated_at",
}

COHORT_LIST_URL_NAME = "api:cohort_course_registration_list"
COHORT_DETAIL_URL_NAME = "api:cohort_course_registration_detail"

COHORT_EXPECTED_FIELDS = {
    "id",
    "course_id",
    "course_title",
    "cohort_id",
    "cohort_name",
    "is_active",
    "registered_at",
    "updated_at",
}

# One param per registration endpoint: list URL name, detail URL name, the
# factory and the exact field set a row carries.
ENDPOINTS = [
    pytest.param(
        LEARNER_LIST_URL_NAME,
        LEARNER_DETAIL_URL_NAME,
        LearnerCourseRegistrationFactory,
        LEARNER_EXPECTED_FIELDS,
        id="learner",
    ),
    pytest.param(
        COHORT_LIST_URL_NAME,
        COHORT_DETAIL_URL_NAME,
        CohortCourseRegistrationFactory,
        COHORT_EXPECTED_FIELDS,
        id="cohort",
    ),
]
ENDPOINT_PARAMS = ("list_name", "detail_name", "factory", "expected_fields")


@pytest.fixture
def auth(mock_site_context) -> dict[str, str]:
    return bearer_auth_for(ApiScope.REGISTRATIONS_AND_PROGRESS)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _detail(
    client: APIClient,
    auth: dict[str, str],
    registration: LearnerCourseRegistration,
    detail_name: str = LEARNER_DETAIL_URL_NAME,
) -> dict[str, object]:
    row: dict[str, object] = client.get(
        reverse(detail_name, args=[registration.pk]), headers=auth
    ).json()
    return row


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_a_key_without_the_scope_is_403_naming_the_scope(
    client, mock_site_context, list_name, detail_name, factory, expected_fields
):
    response = client.get(reverse(list_name), headers=bearer_auth_for(ApiScope.USERS))

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This API key does not have the registrations_and_progress API scope."
    )


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_no_key_is_401(
    client, mock_site_context, list_name, detail_name, factory, expected_fields
):
    response = client.get(reverse(list_name))

    assert response.status_code == 401


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_a_list_row_carries_exactly_the_contract_fields(
    client, auth, list_name, detail_name, factory, expected_fields
):
    factory()

    row = client.get(reverse(list_name), headers=auth).json()["results"][0]

    assert set(row) == expected_fields


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_another_sites_rows_are_absent_from_the_list(
    client, auth, mock_site_context, list_name, detail_name, factory, expected_fields
):
    mine = factory()
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        factory()

    listed = client.get(reverse(list_name), headers=auth).json()["results"]

    assert [row["id"] for row in listed] == [str(mine.pk)]


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_another_sites_row_detail_is_404(
    client, auth, mock_site_context, list_name, detail_name, factory, expected_fields
):
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        theirs = factory()

    response = client.get(reverse(detail_name, args=[theirs.pk]), headers=auth)

    assert response.status_code == 404


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_an_inactive_row_appears_with_is_active_false(
    client, auth, list_name, detail_name, factory, expected_fields
):
    registration = factory(is_active=False)

    row = client.get(reverse(detail_name, args=[registration.pk]), headers=auth).json()

    assert row["is_active"] is False


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_updated_since_returns_only_rows_at_or_after_it(
    client, auth, list_name, detail_name, factory, expected_fields
):
    old = factory()
    new = factory()
    model = type(old)
    model._base_manager.filter(pk=old.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    model._base_manager.filter(pk=new.pk).update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    body = client.get(
        reverse(list_name), {"updated_since": "2025-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [str(new.pk)]


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_rows_sharing_one_updated_at_come_back_once_each_across_pages(
    client, auth, settings, list_name, detail_name, factory, expected_fields
):
    settings.API_PAGE_SIZE = 2
    registrations = factory.create_batch(5)
    type(registrations[0])._base_manager.update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    pages = collect_pages(client, reverse(list_name), auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert sorted(ids) == sorted(str(registration.pk) for registration in registrations)


def _query_count(
    client: APIClient, auth: dict[str, str], list_name: str, page_size: int
) -> int:
    with CaptureQueriesContext(connection) as queries:
        client.get(reverse(list_name), {"page_size": page_size}, headers=auth)
    return len(queries)


@pytest.mark.parametrize(ENDPOINT_PARAMS, ENDPOINTS)
def test_the_query_count_does_not_grow_with_the_page_size(
    client, auth, list_name, detail_name, factory, expected_fields
):
    factory.create_batch(6)
    _query_count(client, auth, list_name, 50)  # the first request pays one-off lookups

    small = _query_count(client, auth, list_name, 2)
    large = _query_count(client, auth, list_name, 50)

    assert small == large


def test_user_columns_carry_the_users_values(client, auth):
    user = UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")
    registration = LearnerCourseRegistrationFactory(learner=LearnerFactory(user=user))

    row = _detail(client, auth, registration)

    assert row["user_id"] == user.pk
    assert row["user_email"] == "ada@example.com"
    assert row["user_first_name"] == "Ada"
    assert row["user_last_name"] == "Lovelace"


def test_a_user_with_no_names_shows_empty_strings(client, auth):
    user = UserFactory(first_name="", last_name="")
    registration = LearnerCourseRegistrationFactory(learner=LearnerFactory(user=user))

    row = _detail(client, auth, registration)

    assert row["user_first_name"] == ""
    assert row["user_last_name"] == ""


def test_the_organisation_is_flattened_to_its_id_and_name(client, auth):
    organisation = OrganisationFactory(name="Acme School")
    registration = LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation)
    )

    row = _detail(client, auth, registration)

    assert row["organisation_id"] == str(organisation.pk)
    assert row["organisation_name"] == "Acme School"


def test_the_course_title_is_carried(client, auth):
    registration = LearnerCourseRegistrationFactory(
        course=CourseFactory(title="Algebra")
    )

    row = _detail(client, auth, registration)

    assert row["course_id"] == str(registration.course_id)
    assert row["course_title"] == "Algebra"


def test_self_registered_is_returned_as_given(client, auth):
    registration = LearnerCourseRegistrationFactory(self_registered=True)

    row = _detail(client, auth, registration)

    assert row["self_registered"] is True


def _change_user_email(registration: LearnerCourseRegistration) -> None:
    registration.learner.user.email = "changed@example.com"
    registration.learner.user.save()


def _change_user_first_name(registration: LearnerCourseRegistration) -> None:
    registration.learner.user.first_name = "Changed"
    registration.learner.user.save()


def _change_organisation_name(registration: LearnerCourseRegistration) -> None:
    registration.learner.organisation.name = "Changed"
    registration.learner.organisation.save()


def _change_course_title(registration: LearnerCourseRegistration) -> None:
    registration.course.title = "Changed"
    registration.course.save()


@pytest.mark.parametrize(
    ("change", "field", "expected"),
    [
        pytest.param(
            _change_user_email, "user_email", "changed@example.com", id="user-email"
        ),
        pytest.param(
            _change_user_first_name, "user_first_name", "Changed", id="user-first-name"
        ),
        pytest.param(
            _change_organisation_name,
            "organisation_name",
            "Changed",
            id="organisation-name",
        ),
        pytest.param(
            _change_course_title, "course_title", "Changed", id="course-title"
        ),
    ],
)
def test_a_change_to_a_flattened_row_shows_without_moving_updated_at(
    client, auth, change, field, expected
):
    registration = LearnerCourseRegistrationFactory()
    before = _detail(client, auth, registration)["updated_at"]

    change(registration)
    after = _detail(client, auth, registration)

    assert after[field] == expected
    assert after["updated_at"] == before


def test_deactivating_a_registration_shows_up_in_the_next_updated_since_pull(
    client, auth
):
    registration = LearnerCourseRegistrationFactory()
    LearnerCourseRegistration._base_manager.filter(pk=registration.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    pulled_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    deactivate_registration(registration.learner, registration.course)
    body = client.get(
        reverse(LEARNER_LIST_URL_NAME), {"updated_since": pulled_at}, headers=auth
    ).json()

    assert [(row["id"], row["is_active"]) for row in body["results"]] == [
        (str(registration.pk), False)
    ]


def test_the_cohort_is_flattened_to_its_id_and_name(client, auth):
    cohort = CohortFactory(name="Grade 9")
    registration = CohortCourseRegistrationFactory(cohort=cohort)

    row = _detail(client, auth, registration, COHORT_DETAIL_URL_NAME)

    assert row["cohort_id"] == str(cohort.pk)
    assert row["cohort_name"] == "Grade 9"


def _change_cohort_name(registration: CohortCourseRegistration) -> None:
    registration.cohort.name = "Changed"
    registration.cohort.save()


@pytest.mark.parametrize(
    ("change", "field"),
    [
        pytest.param(_change_cohort_name, "cohort_name", id="cohort-name"),
        pytest.param(_change_course_title, "course_title", id="course-title"),
    ],
)
def test_a_change_to_a_flattened_cohort_row_shows_without_moving_updated_at(
    client, auth, change, field
):
    registration = CohortCourseRegistrationFactory()
    before = _detail(client, auth, registration, COHORT_DETAIL_URL_NAME)["updated_at"]

    change(registration)
    after = _detail(client, auth, registration, COHORT_DETAIL_URL_NAME)

    assert after[field] == "Changed"
    assert after["updated_at"] == before


def test_deactivating_a_cohort_registration_shows_up_in_the_next_updated_since_pull(
    client, auth
):
    registration = CohortCourseRegistrationFactory()
    CohortCourseRegistration._base_manager.filter(pk=registration.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    pulled_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    deactivate_cohort_registration(registration)
    body = client.get(
        reverse(COHORT_LIST_URL_NAME), {"updated_since": pulled_at}, headers=auth
    ).json()

    assert [(row["id"], row["is_active"]) for row in body["results"]] == [
        (str(registration.pk), False)
    ]
