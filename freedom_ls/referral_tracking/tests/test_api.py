"""The referral endpoints, through a real key on the test client."""

from __future__ import annotations

import json
from base64 import urlsafe_b64encode
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import collect_pages
from freedom_ls.referral_tracking.factories import (
    FirstTouchCountFactory,
    ReferralCodeFactory,
    ReferralCodeHitFactory,
    SignupAttributionFactory,
)
from freedom_ls.referral_tracking.models import (
    FirstTouchCount,
    ReferralCode,
    ReferralCodeHit,
    SignupAttribution,
)
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
    pytest.param(
        "api:referral_code_hit_list",
        "api:referral_code_hit_detail",
        ReferralCodeHitFactory,
        "ReferralCodeHit",
        {
            "id",
            "referral_code",
            "referral_code_text",
            "door",
            "is_machine_fetch",
            "hit_at",
        },
        id="referral_code_hits",
    ),
    pytest.param(
        "api:signup_attribution_list",
        "api:signup_attribution_detail",
        SignupAttributionFactory,
        "SignupAttribution",
        {
            "id",
            "user",
            "user_email",
            "advert_code",
            "referral_code",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "gclid",
            "gbraid",
            "wbraid",
            "fbclid",
            "landing_path",
            "referer",
            "raw_query",
            "first_seen",
            "signed_up_at",
        },
        id="signup_attributions",
    ),
    pytest.param(
        "api:first_touch_count_list",
        "api:first_touch_count_detail",
        FirstTouchCountFactory,
        "FirstTouchCount",
        {
            "id",
            "day",
            "advert_code",
            "referral_code",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
            "is_overflow",
            "key_hash",
            "count",
        },
        id="first_touch_counts",
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


HITS_URL_NAME = "api:referral_code_hit_list"
HIT_INSTANT = datetime(2030, 1, 1, tzinfo=UTC)


def test_a_hit_row_carries_its_codes_id_and_text(client, auth):
    code = ReferralCodeFactory()
    ReferralCodeHitFactory(referral_code=code)

    row = client.get(reverse(HITS_URL_NAME), headers=auth).json()["results"][0]

    assert row["referral_code"] == str(code.pk)
    assert row["referral_code_text"] == code.code


def test_a_hit_row_renders_the_door_as_stored(client, auth):
    ReferralCodeHitFactory()

    row = client.get(reverse(HITS_URL_NAME), headers=auth).json()["results"][0]

    assert row["door"] == "go"


def test_a_hit_row_renders_is_machine_fetch_as_a_json_boolean(client, auth):
    ReferralCodeHitFactory(is_machine_fetch=False)

    row = client.get(reverse(HITS_URL_NAME), headers=auth).json()["results"][0]

    assert row["is_machine_fetch"] is False


def test_a_page_of_hits_does_not_query_per_row(
    client, auth, django_assert_max_num_queries
):
    code = ReferralCodeFactory()
    ReferralCodeHitFactory.create_batch(20, referral_code=code)

    with django_assert_max_num_queries(8):
        response = client.get(reverse(HITS_URL_NAME), headers=auth)

    assert len(response.json()["results"]) == 20


def test_1500_hits_with_one_hit_at_page_without_loss_or_repeat(
    client, auth, settings, mock_site_context
):
    settings.API_MAX_PAGE_SIZE = 500
    code = ReferralCodeFactory()
    rows = ReferralCodeHitFactory.build_batch(1500, referral_code=code)
    ReferralCodeHit._base_manager.bulk_create(rows)
    ReferralCodeHit._base_manager.update(hit_at=HIT_INSTANT)

    pages = collect_pages(client, reverse(HITS_URL_NAME) + "?page_size=500", auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert len(ids) == 1500
    assert len(set(ids)) == 1500


def test_hits_come_back_in_hit_at_order_across_pages(client, auth, settings):
    settings.API_PAGE_SIZE = 2
    first, second, third = (ReferralCodeHitFactory() for _ in range(3))
    for hit, day in ((first, 3), (second, 2), (third, 1)):
        ReferralCodeHit._base_manager.filter(pk=hit.pk).update(
            hit_at=datetime(2030, 1, day, tzinfo=UTC)
        )

    pages = collect_pages(client, reverse(HITS_URL_NAME), auth)

    assert [[row["id"] for row in page["results"]] for page in pages] == [
        [str(third.pk), str(second.pk)],
        [str(first.pk)],
    ]


def test_updated_since_includes_a_hit_at_that_instant_and_excludes_one_before(
    client, auth
):
    at = ReferralCodeHitFactory()
    before = ReferralCodeHitFactory()
    ReferralCodeHit._base_manager.filter(pk=at.pk).update(hit_at=HIT_INSTANT)
    ReferralCodeHit._base_manager.filter(pk=before.pk).update(
        hit_at=datetime(2029, 12, 31, 23, 59, 59, tzinfo=UTC)
    )

    body = client.get(
        reverse(HITS_URL_NAME), {"updated_since": "2030-01-01T00:00:00Z"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [str(at.pk)]


def test_a_naive_updated_since_on_hits_is_400_naming_the_parameter(client, auth):
    response = client.get(
        reverse(HITS_URL_NAME), {"updated_since": "2030-01-01T00:00:00"}, headers=auth
    )

    assert response.status_code == 400
    assert "updated_since" in response.json()


def test_the_next_link_keeps_updated_since_and_page_size(client, auth, settings):
    settings.API_PAGE_SIZE = 2
    for hit in ReferralCodeHitFactory.create_batch(3):
        ReferralCodeHit._base_manager.filter(pk=hit.pk).update(hit_at=HIT_INSTANT)

    body = client.get(
        reverse(HITS_URL_NAME),
        {"updated_since": "2030-01-01T00:00:00Z", "page_size": 2},
        headers=auth,
    ).json()

    assert "updated_since=2030-01-01T00%3A00%3A00Z" in body["next"]
    assert "page_size=2" in body["next"]


ATTRIBUTIONS_URL_NAME = "api:signup_attribution_list"
WITHHELD_FIELDS = {"client_ip", "user_agent", "ga_cookie", "fbp_cookie", "fbc_cookie"}


def test_an_attribution_row_never_carries_a_withheld_field_on_the_list(client, auth):
    SignupAttributionFactory(
        client_ip="203.0.113.7",
        user_agent="Mozilla",
        ga_cookie="GA1.2",
        fbp_cookie="fb.1.1",
        fbc_cookie="fb.1.2",
    )

    row = client.get(reverse(ATTRIBUTIONS_URL_NAME), headers=auth).json()["results"][0]

    assert WITHHELD_FIELDS.isdisjoint(row)


def test_an_attribution_row_never_carries_a_withheld_field_on_the_detail(client, auth):
    attribution = SignupAttributionFactory(
        client_ip="203.0.113.7",
        user_agent="Mozilla",
        ga_cookie="GA1.2",
        fbp_cookie="fb.1.1",
        fbc_cookie="fb.1.2",
    )

    row = client.get(
        reverse("api:signup_attribution_detail", args=[attribution.pk]), headers=auth
    ).json()

    assert WITHHELD_FIELDS.isdisjoint(row)


def test_an_attribution_row_carries_the_users_id_and_email(client, auth):
    attribution = SignupAttributionFactory()

    row = client.get(reverse(ATTRIBUTIONS_URL_NAME), headers=auth).json()["results"][0]

    assert row["user"] == attribution.user.pk
    assert row["user_email"] == attribution.user.email


def test_an_attribution_row_returns_a_blank_field_as_an_empty_string(client, auth):
    SignupAttributionFactory(utm_source="")

    row = client.get(reverse(ATTRIBUTIONS_URL_NAME), headers=auth).json()["results"][0]

    assert row["utm_source"] == ""


def test_an_attribution_row_returns_the_captured_referral_code_text_without_a_code(
    client, auth
):
    SignupAttributionFactory(referral_code="PARTNER")

    row = client.get(reverse(ATTRIBUTIONS_URL_NAME), headers=auth).json()["results"][0]

    assert row["referral_code"] == "PARTNER"


def test_a_page_of_attributions_does_not_query_per_row(
    client, auth, django_assert_max_num_queries
):
    SignupAttributionFactory.create_batch(20)

    with django_assert_max_num_queries(8):
        response = client.get(reverse(ATTRIBUTIONS_URL_NAME), headers=auth)

    assert len(response.json()["results"]) == 20


def test_attributions_come_back_in_signed_up_at_order_across_pages(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    first, second, third = (SignupAttributionFactory() for _ in range(3))
    for attribution, day in ((first, 3), (second, 2), (third, 1)):
        SignupAttribution._base_manager.filter(pk=attribution.pk).update(
            signed_up_at=datetime(2030, 1, day, tzinfo=UTC)
        )

    pages = collect_pages(client, reverse(ATTRIBUTIONS_URL_NAME), auth)

    assert [[row["id"] for row in page["results"]] for page in pages] == [
        [str(third.pk), str(second.pk)],
        [str(first.pk)],
    ]


def test_updated_since_includes_an_attribution_at_that_instant_and_excludes_one_before(
    client, auth
):
    at = SignupAttributionFactory()
    before = SignupAttributionFactory()
    SignupAttribution._base_manager.filter(pk=at.pk).update(signed_up_at=HIT_INSTANT)
    SignupAttribution._base_manager.filter(pk=before.pk).update(
        signed_up_at=datetime(2029, 12, 31, 23, 59, 59, tzinfo=UTC)
    )

    body = client.get(
        reverse(ATTRIBUTIONS_URL_NAME),
        {"updated_since": "2030-01-01T00:00:00Z"},
        headers=auth,
    ).json()

    assert [row["id"] for row in body["results"]] == [str(at.pk)]


def test_a_naive_updated_since_on_attributions_is_400_naming_the_parameter(
    client, auth
):
    response = client.get(
        reverse(ATTRIBUTIONS_URL_NAME),
        {"updated_since": "2030-01-01T00:00:00"},
        headers=auth,
    )

    assert response.status_code == 400
    assert "updated_since" in response.json()


def test_the_attributions_next_link_keeps_updated_since_and_page_size(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    for attribution in SignupAttributionFactory.create_batch(3):
        SignupAttribution._base_manager.filter(pk=attribution.pk).update(
            signed_up_at=HIT_INSTANT
        )

    body = client.get(
        reverse(ATTRIBUTIONS_URL_NAME),
        {"updated_since": "2030-01-01T00:00:00Z", "page_size": 2},
        headers=auth,
    ).json()

    assert "updated_since=2030-01-01T00%3A00%3A00Z" in body["next"]
    assert "page_size=2" in body["next"]


COUNTS_URL_NAME = "api:first_touch_count_list"
COUNT_DAY = date(2030, 1, 1)


def _cursor(payload: object) -> str:
    return urlsafe_b64encode(json.dumps(payload).encode()).decode()


def test_a_count_row_renders_its_day_as_an_iso_date(client, auth):
    FirstTouchCountFactory(day=COUNT_DAY)

    row = client.get(reverse(COUNTS_URL_NAME), headers=auth).json()["results"][0]

    assert row["day"] == "2030-01-01"


def test_a_count_row_renders_is_overflow_as_a_json_boolean(client, auth):
    FirstTouchCountFactory(is_overflow=False)

    row = client.get(reverse(COUNTS_URL_NAME), headers=auth).json()["results"][0]

    assert row["is_overflow"] is False


def test_a_count_row_renders_count_as_an_integer(client, auth):
    FirstTouchCountFactory(count=7)

    row = client.get(reverse(COUNTS_URL_NAME), headers=auth).json()["results"][0]

    assert row["count"] == 7


def test_a_count_row_returns_a_blank_field_as_an_empty_string(client, auth):
    FirstTouchCountFactory(utm_source="")

    row = client.get(reverse(COUNTS_URL_NAME), headers=auth).json()["results"][0]

    assert row["utm_source"] == ""


def test_1500_counts_on_one_day_page_without_loss_or_repeat(
    client, auth, settings, mock_site_context
):
    settings.API_MAX_PAGE_SIZE = 500
    rows = FirstTouchCountFactory.build_batch(1500, day=COUNT_DAY)
    FirstTouchCount._base_manager.bulk_create(rows)

    pages = collect_pages(client, reverse(COUNTS_URL_NAME) + "?page_size=500", auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert len(ids) == 1500
    assert len(set(ids)) == 1500


def test_counts_come_back_in_day_order_across_pages(client, auth, settings):
    settings.API_PAGE_SIZE = 2
    latest = FirstTouchCountFactory(day=date(2030, 1, 3))
    middle = FirstTouchCountFactory(day=date(2030, 1, 2))
    earliest = FirstTouchCountFactory(day=date(2030, 1, 1))

    pages = collect_pages(client, reverse(COUNTS_URL_NAME), auth)

    assert [[row["id"] for row in page["results"]] for page in pages] == [
        [str(earliest.pk), str(middle.pk)],
        [str(latest.pk)],
    ]


@pytest.mark.parametrize(
    "cursor",
    [
        pytest.param(
            _cursor(["day", "2030-01-01T00:00:00+00:00", str(uuid4())]),
            id="datetime_on_a_date_column",
        ),
        pytest.param(_cursor(["day", "20300101", str(uuid4())]), id="compact_date"),
        pytest.param("a" * 513, id="too_long"),
    ],
)
def test_a_cursor_the_api_did_not_issue_is_400_on_counts(client, auth, cursor):
    response = client.get(reverse(COUNTS_URL_NAME), {"cursor": cursor}, headers=auth)

    assert response.status_code == 400
    assert response.json() == {"cursor": ["The cursor is not one this API issued."]}


def test_a_cursor_issued_by_another_endpoint_is_400(client, auth):
    ReferralCodeFactory.create_batch(2)
    next_link = client.get(
        reverse("api:referral_code_list"), {"page_size": 1}, headers=auth
    ).json()["next"]
    cursor = parse_qs(urlsplit(next_link).query)["cursor"][0]

    response = client.get(reverse(HITS_URL_NAME), {"cursor": cursor}, headers=auth)

    assert response.status_code == 400
    assert response.json() == {"cursor": ["The cursor is not one this API issued."]}


def test_day_since_includes_a_count_on_that_day_and_excludes_an_earlier_one(
    client, auth
):
    on_the_day = FirstTouchCountFactory(day=date(2030, 1, 2))
    FirstTouchCountFactory(day=COUNT_DAY)

    body = client.get(
        reverse(COUNTS_URL_NAME), {"day_since": "2030-01-02"}, headers=auth
    ).json()

    assert [row["id"] for row in body["results"]] == [str(on_the_day.pk)]


@pytest.mark.parametrize("value", ["2030-01-02T00:00:00", "2030-1-2", "not-a-date"])
def test_a_day_since_that_is_not_a_date_is_400_naming_the_parameter(
    client, auth, value
):
    response = client.get(reverse(COUNTS_URL_NAME), {"day_since": value}, headers=auth)

    assert response.status_code == 400
    assert "day_since" in response.json()


def test_the_counts_next_link_keeps_day_since_and_page_size(client, auth, settings):
    settings.API_PAGE_SIZE = 2
    FirstTouchCountFactory.create_batch(3, day=COUNT_DAY)

    body = client.get(
        reverse(COUNTS_URL_NAME),
        {"day_since": "2030-01-01", "page_size": 2},
        headers=auth,
    ).json()

    assert "day_since=2030-01-01" in body["next"]
    assert "page_size=2" in body["next"]
