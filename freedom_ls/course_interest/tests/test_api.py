"""The course interest endpoint, through a real key on the test client."""

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
from freedom_ls.course_interest.factories import CourseInterestFactory
from freedom_ls.course_interest.models import CourseInterest
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "api:course_interest_list"
DETAIL_URL_NAME = "api:course_interest_detail"

EXPECTED_FIELDS = {
    "id",
    "course_id",
    "course_title",
    "user_id",
    "user_email",
    "user_first_name",
    "user_last_name",
    "created_at",
    "updated_at",
}


@pytest.fixture
def auth(mock_site_context) -> dict[str, str]:
    return bearer_auth_for(ApiScope.REGISTRATIONS_AND_PROGRESS)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _detail(
    client: APIClient, auth: dict[str, str], interest: CourseInterest
) -> dict[str, object]:
    row: dict[str, object] = client.get(
        reverse(DETAIL_URL_NAME, args=[interest.pk]), headers=auth
    ).json()
    return row


def test_a_key_without_the_scope_is_403_naming_the_scope(client, mock_site_context):
    response = client.get(
        reverse(LIST_URL_NAME), headers=bearer_auth_for(ApiScope.USERS)
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This API key does not have the registrations_and_progress API scope."
    )


def test_no_key_is_401(client, mock_site_context):
    response = client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 401


def test_a_list_row_carries_exactly_the_contract_fields(client, auth):
    CourseInterestFactory()

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert set(row) == EXPECTED_FIELDS


def test_id_and_course_id_are_uuid_strings(client, auth):
    interest = CourseInterestFactory()

    row = _detail(client, auth, interest)

    assert row["id"] == str(interest.pk)
    assert row["course_id"] == str(interest.course_id)


def test_user_id_is_the_users_integer_pk(client, auth):
    interest = CourseInterestFactory()

    row = _detail(client, auth, interest)

    assert row["user_id"] == interest.user.pk
    assert isinstance(row["user_id"], int)


def test_timestamps_end_in_z(client, auth):
    interest = CourseInterestFactory()

    row = _detail(client, auth, interest)

    assert str(row["created_at"]).endswith("Z")
    assert str(row["updated_at"]).endswith("Z")


def test_user_columns_carry_the_users_values(client, auth):
    user = UserFactory(email="ada@example.com", first_name="Ada", last_name="Lovelace")
    interest = CourseInterestFactory(user=user)

    row = _detail(client, auth, interest)

    assert row["user_email"] == "ada@example.com"
    assert row["user_first_name"] == "Ada"
    assert row["user_last_name"] == "Lovelace"


def test_a_user_with_no_names_shows_empty_strings(client, auth):
    interest = CourseInterestFactory(user=UserFactory(first_name="", last_name=""))

    row = _detail(client, auth, interest)

    assert row["user_first_name"] == ""
    assert row["user_last_name"] == ""


def test_the_course_title_is_carried(client, auth):
    interest = CourseInterestFactory(course=CourseFactory(title="Algebra"))

    row = _detail(client, auth, interest)

    assert row["course_title"] == "Algebra"


def test_another_sites_rows_are_absent_from_the_list(client, auth, mock_site_context):
    mine = CourseInterestFactory()
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        CourseInterestFactory()

    listed = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"]

    assert [row["id"] for row in listed] == [str(mine.pk)]


def test_another_sites_row_detail_is_404(client, auth, mock_site_context):
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        theirs = CourseInterestFactory()

    response = client.get(reverse(DETAIL_URL_NAME, args=[theirs.pk]), headers=auth)

    assert response.status_code == 404


def test_updated_since_returns_only_rows_at_or_after_it(client, auth):
    old = CourseInterestFactory()
    new = CourseInterestFactory()
    CourseInterest._base_manager.filter(pk=old.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    CourseInterest._base_manager.filter(pk=new.pk).update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    body = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [str(new.pk)]


def test_rows_sharing_one_updated_at_come_back_once_each_across_pages(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    interests = [CourseInterestFactory() for _ in range(5)]
    CourseInterest._base_manager.update(updated_at=datetime(2030, 1, 1, tzinfo=UTC))

    pages = collect_pages(client, reverse(LIST_URL_NAME), auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert sorted(ids) == sorted(str(interest.pk) for interest in interests)


def _query_count(client: APIClient, auth: dict[str, str], page_size: int) -> int:
    with CaptureQueriesContext(connection) as queries:
        client.get(reverse(LIST_URL_NAME), {"page_size": page_size}, headers=auth)
    return len(queries)


def test_the_query_count_does_not_grow_with_the_page_size(client, auth):
    [CourseInterestFactory() for _ in range(6)]
    _query_count(client, auth, 50)  # the first request pays one-off lookups

    small = _query_count(client, auth, 2)
    large = _query_count(client, auth, 50)

    assert small == large


def _change_user_email(interest: CourseInterest) -> None:
    interest.user.email = "changed@example.com"
    interest.user.save()


def _change_user_first_name(interest: CourseInterest) -> None:
    interest.user.first_name = "Changed"
    interest.user.save()


def _change_course_title(interest: CourseInterest) -> None:
    interest.course.title = "Changed"
    interest.course.save()


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
            _change_course_title, "course_title", "Changed", id="course-title"
        ),
    ],
)
def test_a_change_to_the_user_or_course_shows_without_moving_updated_at(
    client, auth, change, field, expected
):
    interest = CourseInterestFactory()
    before = _detail(client, auth, interest)["updated_at"]

    change(interest)
    after = _detail(client, auth, interest)

    assert after[field] == expected
    assert after["updated_at"] == before
