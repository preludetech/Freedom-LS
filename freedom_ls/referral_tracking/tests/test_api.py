"""The referral endpoints, through a real key on the test client."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import collect_pages
from freedom_ls.referral_tracking.factories import ReferralCodeFactory
from freedom_ls.referral_tracking.models import ReferralCode
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

RESOURCES = [
    pytest.param(
        "api:referral_code_list",
        "api:referral_code_detail",
        ReferralCodeFactory,
        "ReferralCode",
        {
            "id",
            "code",
            "label",
            "notes",
            "destination",
            "inactive_destination",
            "is_active",
            "hit_count",
            "last_hit_at",
            "created_at",
        },
        id="referral_codes",
    ),
]


@pytest.fixture
def api_key(mock_site_context):
    return ApiKeyFactory(scopes=[ApiScope.REFERRAL_DATA])


@pytest.fixture
def auth(api_key) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key.issued_key}"}


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.parametrize(
    ("list_name", "detail_name", "factory", "model_name", "expected_fields"), RESOURCES
)
class TestSharedResourceBehaviour:
    def test_a_valid_key_lists_exactly_the_serialized_fields(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        factory()

        body = client.get(reverse(list_name), headers=auth).json()

        assert set(body["results"][0]) == expected_fields
        assert body["next"] is None

    def test_another_sites_row_is_absent_from_the_list_and_404_on_detail(
        self,
        client,
        auth,
        list_name,
        detail_name,
        factory,
        model_name,
        expected_fields,
    ):
        mine = factory()
        with site_context(SiteFactory(name="Other", domain="other.example.com")):
            theirs = factory()

        listed = client.get(reverse(list_name), headers=auth).json()["results"]
        detail = client.get(reverse(detail_name, args=[theirs.pk]), headers=auth)

        assert [row["id"] for row in listed] == [str(mine.pk)]
        assert detail.status_code == 404

    def test_the_detail_returns_the_row_by_its_id(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        row = factory()

        response = client.get(reverse(detail_name, args=[row.pk]), headers=auth)

        assert response.status_code == 200
        assert response.json()["id"] == str(row.pk)

    def test_an_unknown_id_is_404_json(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        response = client.get(reverse(detail_name, args=[uuid4()]), headers=auth)

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"No {model_name} matches the given query.",
            "code": "not_found",
        }

    def test_a_key_without_the_referral_data_scope_is_403_on_the_list(
        self,
        client,
        mock_site_context,
        list_name,
        detail_name,
        factory,
        model_name,
        expected_fields,
    ):
        key = ApiKeyFactory(scopes=[ApiScope.USERS])

        response = client.get(
            reverse(list_name), headers={"Authorization": f"Bearer {key.issued_key}"}
        )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "This API key does not have the referral_data API scope.",
            "code": "permission_denied",
        }

    def test_a_key_without_the_referral_data_scope_is_403_on_a_detail(
        self,
        client,
        mock_site_context,
        list_name,
        detail_name,
        factory,
        model_name,
        expected_fields,
    ):
        row = factory()
        key = ApiKeyFactory(scopes=[ApiScope.USERS])

        response = client.get(
            reverse(detail_name, args=[row.pk]),
            headers={"Authorization": f"Bearer {key.issued_key}"},
        )

        assert response.status_code == 403
        assert response.json() == {
            "detail": "This API key does not have the referral_data API scope.",
            "code": "permission_denied",
        }

    def test_post_on_the_list_is_405_json(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        response = client.post(reverse(list_name), headers=auth)

        assert response.status_code == 405
        assert response.json() == {
            "detail": 'Method "POST" not allowed.',
            "code": "method_not_allowed",
        }

    def test_head_on_the_list_is_200_json_private_and_empty(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        factory()

        response = client.head(reverse(list_name), headers=auth)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"
        assert "private" in response["Cache-Control"]
        assert "no-store" in response["Cache-Control"]
        assert response.content == b""

    def test_options_on_the_list_is_200_with_the_allowed_methods(
        self, client, auth, list_name, detail_name, factory, model_name, expected_fields
    ):
        response = client.options(reverse(list_name), headers=auth)

        assert response.status_code == 200
        assert response["Allow"] == "GET, HEAD, OPTIONS"


def test_no_key_is_401_with_the_bearer_challenge(client, mock_site_context):
    response = client.get(reverse("api:referral_code_list"))

    assert response.status_code == 401
    assert response["WWW-Authenticate"] == 'Bearer realm="api"'


def test_referral_codes_come_back_in_created_at_order_across_pages(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    first, second, third = (ReferralCodeFactory() for _ in range(3))
    for code, day in ((first, 3), (second, 2), (third, 1)):
        ReferralCode._base_manager.filter(pk=code.pk).update(
            created_at=datetime(2030, 1, day, tzinfo=UTC)
        )

    pages = collect_pages(client, reverse("api:referral_code_list"), auth)

    assert [[row["id"] for row in page["results"]] for page in pages] == [
        [str(third.pk), str(second.pk)],
        [str(first.pk)],
    ]


def test_the_counter_is_returned_as_stored(client, auth):
    code = ReferralCodeFactory()
    ReferralCode._base_manager.filter(pk=code.pk).update(hit_count=5)

    row = client.get(reverse("api:referral_code_list"), headers=auth).json()["results"][
        0
    ]

    assert row["hit_count"] == 5


def test_a_code_never_hit_has_a_null_last_hit_at(client, auth):
    ReferralCodeFactory()

    row = client.get(reverse("api:referral_code_list"), headers=auth).json()["results"][
        0
    ]

    assert row["last_hit_at"] is None
