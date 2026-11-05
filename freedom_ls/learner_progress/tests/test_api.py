"""The course progress endpoint, through a real key on the test client."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    TopicFactory,
)
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.api"):
    pytest.skip("freedom_ls.api not installed", allow_module_level=True)

from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import bearer_auth_for, collect_pages
from freedom_ls.learner_progress.factories import (
    CourseProgressFactory,
    TopicProgressFactory,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.tests.helpers import (
    cohort_registration_record,
    inactive_cohort_registration_record,
    inactive_learner_record,
    inactive_learner_registration_record,
    learner_registration_record,
    resolve_ref,
    set_updated_at,
)
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "api:course_progress_list"
DETAIL_URL_NAME = "api:course_progress_detail"

EXPECTED_FIELDS = {
    "id",
    "course_id",
    "course_title",
    "registration_id",
    "registration_kind",
    "progress_percentage",
    "started_at",
    "last_accessed_time",
    "completed_time",
    "updated_at",
}

SINCE = {"updated_since": "2025-01-01T00:00:00Z"}


@pytest.fixture
def auth(mock_site_context) -> dict[str, str]:
    return bearer_auth_for(ApiScope.REGISTRATIONS_AND_PROGRESS)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _listed_ids(client: APIClient, auth: dict[str, str], **params: str) -> list[str]:
    body = client.get(reverse(LIST_URL_NAME), params, headers=auth).json()
    return [row["id"] for row in body["results"]]


def test_a_key_without_the_scope_is_403(client, mock_site_context):
    response = client.get(
        reverse(LIST_URL_NAME), headers=bearer_auth_for(ApiScope.USERS)
    )

    assert response.status_code == 403
    assert response.json()["code"] == "permission_denied"


def test_a_valid_key_lists_exactly_the_serialized_fields(client, auth):
    learner_registration_record()

    body = client.get(reverse(LIST_URL_NAME), headers=auth).json()

    assert set(body["results"][0]) == EXPECTED_FIELDS
    assert body["next"] is None


@pytest.mark.parametrize(
    ("builder", "expected_kind", "registration_id_of"),
    [
        pytest.param(
            learner_registration_record,
            "learner",
            lambda record: record.learner_registration_id,
            id="learner",
        ),
        pytest.param(
            cohort_registration_record,
            "cohort",
            lambda record: record.cohort_registration_id,
            id="cohort",
        ),
    ],
)
def test_a_row_carries_its_registration_kind_and_id(
    client,
    auth,
    builder: Callable[[], CourseProgress],
    expected_kind: str,
    registration_id_of: Callable[[CourseProgress], object],
):
    record = builder()

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert row["registration_kind"] == expected_kind
    assert row["registration_id"] == str(registration_id_of(record))


def test_a_not_started_row_has_null_timestamps_and_zero_progress(client, auth):
    course = CourseFactory(title="Intro")
    record = CourseProgressFactory(course=course)

    row = client.get(reverse(LIST_URL_NAME), headers=auth).json()["results"][0]

    assert (
        row["started_at"],
        row["last_accessed_time"],
        row["completed_time"],
        row["progress_percentage"],
        row["course_id"],
        row["course_title"],
    ) == (None, None, None, 0, str(course.pk), "Intro")
    assert row["id"] == str(record.pk)


@pytest.mark.parametrize(
    "builder",
    [
        inactive_learner_registration_record,
        inactive_cohort_registration_record,
        inactive_learner_record,
    ],
)
def test_rows_under_deactivated_records_are_listed(
    client, auth, builder: Callable[[], CourseProgress]
):
    record = builder()

    assert _listed_ids(client, auth) == [str(record.pk)]


def test_another_sites_rows_are_absent_from_the_list_and_404_on_detail(
    client, auth, mock_site_context
):
    mine = learner_registration_record()
    with site_context(SiteFactory(name="Other", domain="other.example.com")):
        theirs = learner_registration_record()

    detail = client.get(reverse(DETAIL_URL_NAME, args=[theirs.pk]), headers=auth)

    assert _listed_ids(client, auth) == [str(mine.pk)]
    assert detail.status_code == 404


def test_the_detail_returns_one_row(client, auth):
    record = learner_registration_record()

    response = client.get(reverse(DETAIL_URL_NAME, args=[record.pk]), headers=auth)

    assert response.status_code == 200
    assert response.json()["id"] == str(record.pk)


def test_updated_since_returns_rows_at_or_after_it(client, auth):
    old = learner_registration_record()
    new = learner_registration_record()
    boundary = learner_registration_record()
    set_updated_at(old, datetime(2020, 1, 1, tzinfo=UTC))
    set_updated_at(new, datetime(2030, 1, 1, tzinfo=UTC))
    set_updated_at(boundary, datetime(2025, 1, 1, tzinfo=UTC))

    assert sorted(_listed_ids(client, auth, **SINCE)) == sorted(
        [str(new.pk), str(boundary.pk)]
    )


def test_a_naive_updated_since_is_400_naming_the_parameter(client, auth):
    response = client.get(
        reverse(LIST_URL_NAME), {"updated_since": "2025-01-01T00:00:00"}, headers=auth
    )

    assert response.status_code == 400
    assert "updated_since" in response.json()


def test_rows_sharing_one_updated_at_come_back_once_each_across_pages(
    client, auth, settings
):
    settings.API_PAGE_SIZE = 2
    records = [
        learner_registration_record(),
        cohort_registration_record(),
        learner_registration_record(),
        cohort_registration_record(),
        learner_registration_record(),
    ]
    CourseProgress._base_manager.filter(pk__in=[r.pk for r in records]).update(
        updated_at=datetime(2030, 1, 1, tzinfo=UTC)
    )

    pages = collect_pages(client, reverse(LIST_URL_NAME), auth)

    ids = [row["id"] for page in pages for row in page["results"]]
    assert [len(page["results"]) for page in pages] == [2, 2, 1]
    assert len(set(ids)) == 5


def test_completing_a_topic_re_emits_the_row_under_updated_since(client, auth):
    course = CourseFactory()
    record = CourseProgressFactory(course=course)
    item = ContentCollectionItemFactory(
        collection_object=course, child_object=TopicFactory(), order=0
    )
    topic_progress = TopicProgressFactory(
        course_progress=record, collection_item=item, topic=item.child
    )
    set_updated_at(record, datetime(2020, 1, 1, tzinfo=UTC))
    topic_progress.complete_time = timezone.now()
    topic_progress.save()

    body = client.get(reverse(LIST_URL_NAME), SINCE, headers=auth).json()

    assert [(row["id"], row["progress_percentage"]) for row in body["results"]] == [
        (str(record.pk), 100)
    ]


def test_the_schema_types_registration_id_and_registration_kind(client, auth):
    document = client.get(reverse("api:schema"), headers=auth).json()
    component = document["components"]["schemas"]["CourseProgressApi"]["properties"]

    kind = resolve_ref(document, component["registration_kind"])

    assert component["registration_id"] == {
        "type": "string",
        "format": "uuid",
        "readOnly": True,
    }
    assert kind["enum"] == ["learner", "cohort"]
