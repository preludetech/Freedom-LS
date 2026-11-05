"""The course applications endpoint, through a real key on the test client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import collect_pages
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "api:course_application_list"
DETAIL_URL_NAME = "api:course_application_detail"

EXPECTED_FIELDS = [
    "id",
    "applicant_email",
    "applicant_name",
    "is_email_verified",
    "course_id",
    "course_title",
    "is_submitted",
    "submitted_time",
    "created_at",
    "updated_at",
    "answers",
]


@pytest.fixture
def api_key(mock_site_context):
    return ApiKeyFactory(scopes=[ApiScope.COURSE_APPLICATIONS])


@pytest.fixture
def auth(api_key) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key.issued_key}"}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_no_key_is_401_with_the_bearer_challenge(client, mock_site_context):
    response = client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'


@pytest.mark.parametrize("url_name", [LIST_URL_NAME, DETAIL_URL_NAME])
def test_a_key_without_the_scope_is_403_naming_the_scope(
    client, mock_site_context, url_name
):
    application = CourseApplicationFactory()
    key = ApiKeyFactory(scopes=[ApiScope.USERS])
    args = [application.pk] if url_name == DETAIL_URL_NAME else []

    response = client.get(
        reverse(url_name, args=args),
        headers={"Authorization": f"Bearer {key.issued_key}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This API key does not have the course_applications API scope."
    )


@pytest.mark.parametrize("url_name", [LIST_URL_NAME, DETAIL_URL_NAME])
def test_a_key_with_the_scope_is_200(client, auth, url_name):
    application = CourseApplicationFactory()
    args = [application.pk] if url_name == DETAIL_URL_NAME else []

    response = client.get(reverse(url_name, args=args), headers=auth)

    assert response.status_code == 200


def test_another_sites_applications_are_absent_from_the_list_and_404_on_detail(
    client, auth, mock_site_context
):
    mine = CourseApplicationFactory()
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        theirs = CourseApplicationFactory()

    listed = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"]
    detail = client.get(reverse(DETAIL_URL_NAME, args=[theirs.pk]), headers=auth)

    assert [row["id"] for row in listed] == [str(mine.pk)]
    assert detail.status_code == 404


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_methods_are_405(client, auth, method):
    application = CourseApplicationFactory()

    response = getattr(client, method)(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    )

    assert response.status_code == 405


def test_a_list_row_carries_exactly_the_contract_fields_in_order(client, auth):
    CourseApplicationFactory()

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert list(row) == EXPECTED_FIELDS


def test_a_signed_in_applicant_is_verified_and_an_anonymous_one_is_not(client, auth):
    user = UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")
    CourseApplicationFactory(user=user)
    anonymous_applicant = AnonymousApplicantFactory(email="anna@example.com")
    CourseApplicationFactory(
        user=None,
        course=anonymous_applicant.course,
        anonymous_applicant=anonymous_applicant,
    )

    rows = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"]

    by_email = {row["applicant_email"]: row for row in rows}
    assert by_email["ada@example.com"]["applicant_name"] == "Ada Lovelace"
    assert by_email["ada@example.com"]["is_email_verified"] is True
    assert by_email["anna@example.com"]["applicant_name"] == "Anna Applicant"
    assert by_email["anna@example.com"]["is_email_verified"] is False


def test_a_draft_is_not_submitted_and_has_no_submitted_time(client, auth):
    application = CourseApplicationFactory(anonymous_draft=True)

    row = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert row["is_submitted"] is False
    assert row["submitted_time"] is None


def test_an_application_with_no_sitting_was_submitted_when_created(client, auth):
    application = CourseApplicationFactory()

    row = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert row["is_submitted"] is True
    assert row["submitted_time"] == row["created_at"]


def test_answers_are_an_empty_list_when_there_is_no_sitting(client, auth):
    application = CourseApplicationFactory()

    row = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert row["answers"] == []


def test_the_course_is_named_by_id_and_title(client, auth):
    application = CourseApplicationFactory()

    row = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert row["course_id"] == str(application.course_id)
    assert row["course_title"] == application.course.title


def test_the_detail_returns_the_same_object_as_the_list_entry(client, auth):
    application = CourseApplicationFactory()

    listed = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]
    detail = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert detail == listed


def test_applications_sharing_one_updated_at_come_back_once_each_across_pages(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    applications = [CourseApplicationFactory() for _ in range(5)]
    CourseApplication._base_manager.update(updated_at=datetime(2030, 1, 1, tzinfo=UTC))

    pages = collect_pages(client, reverse(LIST_URL_NAME), auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert sorted(ids) == sorted(str(application.pk) for application in applications)


def test_updated_at_round_trips_at_microsecond_precision(client, auth):
    application = CourseApplicationFactory()
    stamp = datetime(2030, 1, 1, 12, 30, 15, 123456, tzinfo=UTC)
    CourseApplication._base_manager.filter(pk=application.pk).update(updated_at=stamp)

    row = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()

    assert datetime.fromisoformat(row["updated_at"]) == stamp


def test_updated_since_returns_only_rows_changed_at_or_after_it(client, auth):
    old = CourseApplicationFactory()
    new = CourseApplicationFactory()
    CourseApplication._base_manager.filter(pk=old.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    CourseApplication._base_manager.filter(pk=new.pk).update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    body = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [str(new.pk)]
