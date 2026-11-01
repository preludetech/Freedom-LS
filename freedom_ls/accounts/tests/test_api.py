"""The users endpoint, through a real key on the test client."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from allauth.account.models import EmailAddress

from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import collect_pages
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "api:user_list"
DETAIL_URL_NAME = "api:user_detail"

EXPECTED_FIELDS = {
    "id",
    "email",
    "first_name",
    "last_name",
    "is_active",
    "is_staff",
    "email_verified",
    "created_at",
    "last_login",
    "updated_at",
}


@pytest.fixture
def api_key(mock_site_context):
    return ApiKeyFactory()


@pytest.fixture
def auth(api_key) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key.issued_key}"}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def test_a_valid_key_lists_exactly_the_serialized_fields(client, auth, api_key):
    UserFactory(email="ada@example.com")

    body = client.get(reverse(LIST_URL_NAME), headers=auth).json()

    assert set(body["results"][0]) == EXPECTED_FIELDS
    assert body["next"] is None


def test_the_list_never_carries_credentials_or_permissions(client, auth):
    UserFactory()

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert {"password", "is_superuser", "groups", "user_permissions"}.isdisjoint(row)


def test_timestamps_carry_a_timezone_and_id_is_an_integer(client, auth):
    user = UserFactory()

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert row["id"] == user.pk
    assert isinstance(row["id"], int)
    assert row["created_at"].endswith("Z")
    assert row["updated_at"].endswith("Z")


def test_another_sites_users_are_absent_from_the_list_and_404_on_detail(
    client, auth, mock_site_context
):
    mine = UserFactory(email="mine@example.com")
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        theirs = UserFactory(email="theirs@example.com")

    listed = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"]
    detail = client.get(reverse(DETAIL_URL_NAME, args=[theirs.pk]), headers=auth)

    assert [row["email"] for row in listed] == [mine.email]
    assert detail.status_code == 404


def test_the_detail_returns_one_user(client, auth):
    user = UserFactory(email="ada@example.com")

    response = client.get(reverse(DETAIL_URL_NAME, args=[user.pk]), headers=auth)

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


def test_pages_are_followed_to_the_end(client, auth, settings):
    settings.API_PAGE_SIZE = 2
    [UserFactory() for _ in range(5)]

    pages = collect_pages(client, reverse(LIST_URL_NAME), auth)

    assert [len(page["results"]) for page in pages] == [2, 2, 1]


def test_a_key_without_the_users_scope_is_403_naming_the_scope(
    client, mock_site_context
):
    key = ApiKeyFactory(scopes=[ApiScope.REFERRAL_DATA])

    response = client.get(
        reverse(LIST_URL_NAME), headers={"Authorization": f"Bearer {key.issued_key}"}
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "This API key does not have the users API scope.",
        "code": "permission_denied",
    }


def test_no_key_is_401_with_the_bearer_challenge(client, mock_site_context):
    response = client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'
    assert response.json()["code"] == "not_authenticated"


def test_a_signed_in_session_with_no_key_is_401(client, mock_site_context):
    client.force_login(UserFactory(superuser=True))

    response = client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 401


def test_a_bad_key_is_401_with_the_one_message(client, mock_site_context):
    response = client.get(
        reverse(LIST_URL_NAME), headers={"Authorization": "Bearer flsk_nope.nope"}
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Invalid API key.",
        "code": "authentication_failed",
    }


def _verified_state(client: APIClient, auth: dict[str, str], user_pk: int) -> bool:
    body = client.get(reverse(DETAIL_URL_NAME, args=[user_pk]), headers=auth).json()
    return bool(body["email_verified"])


def test_email_verified_is_true_for_a_verified_primary_address(client, auth):
    user = UserFactory(email="a@example.com")
    EmailAddress.objects.create(
        user=user, email="a@example.com", verified=True, primary=True
    )

    assert _verified_state(client, auth, user.pk) is True


def test_email_verified_is_false_for_a_verified_non_primary_address_only(client, auth):
    user = UserFactory(email="b@example.com")
    EmailAddress.objects.create(
        user=user, email="other@example.com", verified=True, primary=False
    )

    assert _verified_state(client, auth, user.pk) is False


def test_email_verified_is_false_with_no_address(client, auth):
    user = UserFactory(email="c@example.com")

    assert _verified_state(client, auth, user.pk) is False


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_write_methods_are_405_json(client, auth, method):
    user = UserFactory()

    response = getattr(client, method)(
        reverse(DETAIL_URL_NAME, args=[user.pk]), headers=auth
    )

    assert response.status_code == 405
    assert response.json() == {
        "detail": f'Method "{method.upper()}" not allowed.',
        "code": "method_not_allowed",
    }


def test_an_unknown_id_is_404_json(client, auth):
    response = client.get(reverse(DETAIL_URL_NAME, args=[999999]), headers=auth)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No User matches the given query.",
        "code": "not_found",
    }


def test_head_matches_get_with_an_empty_body(client, auth):
    UserFactory()
    url = reverse(LIST_URL_NAME)

    got = client.get(url, headers=auth)
    head = client.head(url, headers=auth)

    assert head.status_code == got.status_code
    assert head["Content-Type"] == got["Content-Type"]
    assert head["Cache-Control"] == got["Cache-Control"]
    assert head.content == b""


def test_options_is_200_with_allow_and_no_actions(client, auth):
    response = client.options(reverse(LIST_URL_NAME), headers=auth)

    assert response.status_code == 200
    assert response["Allow"] == "GET, HEAD, OPTIONS"
    assert response.json() == {"name": "User Api List"}


def test_a_page_of_twenty_users_stays_under_a_query_bound(
    client, auth, django_assert_max_num_queries
):
    [UserFactory() for _ in range(20)]

    with django_assert_max_num_queries(8):
        response = client.get(reverse(LIST_URL_NAME), headers=auth)

    assert len(response.json()["results"]) == 20


def test_users_sharing_one_updated_at_come_back_once_each_across_pages(
    client, auth, api_key
):
    User.objects.bulk_create(
        [User(email=f"bulk{n}@example.com", site=api_key.site) for n in range(1500)]
    )
    User._base_manager.update(updated_at=datetime(2030, 1, 1, tzinfo=UTC))

    pages = collect_pages(client, reverse(LIST_URL_NAME), auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert len(ids) == 1500
    assert len(set(ids)) == 1500


def test_updated_since_returns_only_rows_changed_at_or_after_it(client, auth):
    old = UserFactory()
    new = UserFactory()
    User._base_manager.filter(pk=old.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    User._base_manager.filter(pk=new.pk).update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    body = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [new.pk]


def test_a_naive_updated_since_is_400_naming_the_parameter(client, auth):
    response = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00"}, headers=auth
    )

    assert response.status_code == 400
    assert "updated_since" in response.json()


def test_a_user_verified_after_updated_since_is_in_the_filtered_list(client, auth):
    user = UserFactory()
    User._base_manager.filter(pk=user.pk).update(
        updated_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
    EmailAddress.objects.create(
        user=user, email=user.email, verified=True, primary=True
    )

    body = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [user.pk]
