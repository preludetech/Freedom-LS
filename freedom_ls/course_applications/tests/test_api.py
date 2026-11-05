"""The course applications endpoint, through a real key on the test client."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.api.factories import ApiKeyFactory
from freedom_ls.api.scopes import ApiScope
from freedom_ls.api.tests.helpers import collect_pages
from freedom_ls.course_applications.api import (
    CourseApplicationApiSerializer,
    CourseApplicationApiViewSet,
)
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.form_engine.factories import (
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import QuestionAnswer
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

LIST_URL_NAME = "api:course_application_list"
DETAIL_URL_NAME = "api:course_application_detail"

ENDPOINT_URLS = [
    pytest.param(lambda application: reverse(LIST_URL_NAME), id="list"),
    pytest.param(
        lambda application: reverse(DETAIL_URL_NAME, args=[application.pk]),
        id="detail",
    ),
]

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


@pytest.mark.parametrize("endpoint_url", ENDPOINT_URLS)
def test_a_key_without_the_scope_is_403_naming_the_scope(
    client, mock_site_context, endpoint_url
):
    application = CourseApplicationFactory()
    key = ApiKeyFactory(scopes=[ApiScope.USERS])

    response = client.get(
        endpoint_url(application),
        headers={"Authorization": f"Bearer {key.issued_key}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "This API key does not have the course_applications API scope."
    )


@pytest.mark.parametrize("endpoint_url", ENDPOINT_URLS)
def test_a_key_with_the_scope_is_200(client, auth, endpoint_url):
    application = CourseApplicationFactory()

    response = client.get(endpoint_url(application), headers=auth)

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


QUERY_BOUND = 6

EXPECTED_ANSWER_FIELDS = ["question_id", "question_text", "question_type", "value"]


def _typing(text: str) -> Callable[[QuestionAnswer], None]:
    def fill(answer: QuestionAnswer) -> None:
        answer.text_answer = text
        answer.save()

    return fill


def _selecting(*option_texts: str) -> Callable[[QuestionAnswer], None]:
    def fill(answer: QuestionAnswer) -> None:
        options = [
            QuestionOptionFactory(question=answer.question, text=text, order=order)
            for order, text in enumerate(option_texts)
        ]
        answer.selected_options.add(*options)

    return fill


def _attaching(original_filename: str) -> Callable[[QuestionAnswer], None]:
    def fill(answer: QuestionAnswer) -> None:
        QuestionAnswerFileFactory(answer=answer, original_filename=original_filename)

    return fill


def _answer_nothing(answer: QuestionAnswer) -> None:
    """Leave the answer row empty."""


def _application_answering(
    question_type: str,
    fill: Callable[[QuestionAnswer], None],
    **question_fields: object,
) -> tuple[CourseApplication, QuestionAnswer]:
    """An anonymous application whose sitting holds one answer to a question of the type."""
    sitting = FormProgressFactory(user=None)
    question = FormQuestionFactory(
        form_page=FormPageFactory(form=sitting.form),
        type=question_type,
        **question_fields,
    )
    answer = cast(
        QuestionAnswer,
        QuestionAnswerFactory(form_progress=sitting, question=question),
    )
    fill(answer)
    application = cast(
        CourseApplication,
        CourseApplicationFactory(anonymous=True, form_progress=sitting),
    )
    return application, answer


def _application_with_every_kind_of_answer() -> CourseApplication:
    """An anonymous application with a text, a checkbox, a choice and a file answer."""
    sitting = FormProgressFactory(user=None)
    page = FormPageFactory(form=sitting.form)
    answers_by_type = {
        "short_text": _typing("Ada"),
        "checkboxes": _selecting("Red", "Blue"),
        "multiple_choice": _selecting("Yes"),
        "file_upload": _attaching("id.png"),
    }
    for order, (question_type, fill) in enumerate(answers_by_type.items()):
        question = FormQuestionFactory(form_page=page, type=question_type, order=order)
        fill(QuestionAnswerFactory(form_progress=sitting, question=question))
    return cast(
        CourseApplication,
        CourseApplicationFactory(anonymous=True, form_progress=sitting),
    )


def _answers_of(client: APIClient, auth: dict[str, str], application) -> list[dict]:
    body = client.get(
        reverse(DETAIL_URL_NAME, args=[application.pk]), headers=auth
    ).json()
    answers: list[dict] = body["answers"]
    return answers


def test_an_answer_entry_carries_exactly_the_contract_fields_in_order(client, auth):
    application, _ = _application_answering("short_text", _typing("Ada"))

    entry = _answers_of(client, auth, application)[0]

    assert list(entry) == EXPECTED_ANSWER_FIELDS


def test_an_answer_entry_names_its_question(client, auth):
    application, answer = _application_answering(
        "short_text", _typing("Ada"), question="Your name"
    )

    entry = _answers_of(client, auth, application)[0]

    assert entry["question_id"] == str(answer.question_id)
    assert entry["question_text"] == "Your name"
    assert entry["question_type"] == "short_text"


@pytest.mark.parametrize(
    ("question_type", "fill", "expected"),
    [
        pytest.param("short_text", _typing("Ada"), "Ada", id="short_text"),
        pytest.param("short_text", _answer_nothing, None, id="empty_text"),
        pytest.param("date", _typing("2026-01-02"), "2026-01-02", id="date"),
        pytest.param(
            "checkboxes", _selecting("Red", "Blue"), ["Red", "Blue"], id="checkboxes"
        ),
        pytest.param("checkboxes", _answer_nothing, None, id="checkboxes_none"),
        pytest.param("multiple_choice", _selecting("Yes"), "Yes", id="choice"),
        pytest.param(
            "multiple_choice", _selecting("A", "B"), "A; B", id="choice_two_options"
        ),
        pytest.param("dropdown", _selecting("North"), "North", id="dropdown"),
        pytest.param("file_upload", _attaching("id.png"), "id.png", id="file"),
        pytest.param("file_upload", _answer_nothing, None, id="file_none"),
        pytest.param("file_upload", _attaching(""), None, id="file_empty_name"),
    ],
)
def test_an_answers_value_by_question_type(client, auth, question_type, fill, expected):
    application, _ = _application_answering(question_type, fill)

    entry = _answers_of(client, auth, application)[0]

    assert entry["value"] == expected


def test_a_file_answer_exposes_no_storage_key_path_or_url(client, auth):
    application, answer = _application_answering("file_upload", _attaching("id.png"))

    entry = _answers_of(client, auth, application)[0]

    serialised = json.dumps(entry)
    stored_file = answer.answer_file.file
    assert str(stored_file.name) not in serialised
    assert stored_file.url not in serialised


def test_answers_come_back_by_page_then_question_order(client, auth):
    sitting = FormProgressFactory(user=None)
    first_page = FormPageFactory(form=sitting.form, order=0)
    second_page = FormPageFactory(form=sitting.form, order=1)
    questions = [
        FormQuestionFactory(form_page=second_page, order=0, question="Third"),
        FormQuestionFactory(form_page=first_page, order=1, question="Second"),
        FormQuestionFactory(form_page=first_page, order=0, question="First"),
    ]
    for question in questions:
        QuestionAnswerFactory(form_progress=sitting, question=question)
    application = CourseApplicationFactory(anonymous=True, form_progress=sitting)

    entries = _answers_of(client, auth, application)

    assert [entry["question_text"] for entry in entries] == [
        "First",
        "Second",
        "Third",
    ]


def test_an_unanswered_question_has_no_entry(client, auth):
    sitting = FormProgressFactory(user=None)
    FormQuestionFactory(form_page=FormPageFactory(form=sitting.form))
    application = CourseApplicationFactory(anonymous=True, form_progress=sitting)

    assert _answers_of(client, auth, application) == []


def test_answers_are_complete_when_the_ambient_site_is_not_the_applications_site(
    mock_site_context,
):
    _application_with_every_kind_of_answer()
    other = SiteFactory(name="Other", domain="other.example.com")

    with site_context(other):
        rows = CourseApplicationApiSerializer(
            CourseApplicationApiViewSet().get_queryset(), many=True
        ).data

    assert [entry["value"] for entry in rows[0]["answers"]] == [
        "Ada",
        ["Red", "Blue"],
        "Yes",
        "id.png",
    ]


def _query_count_of_list(client: APIClient, auth: dict[str, str]) -> int:
    with CaptureQueriesContext(connection) as queries:
        client.get(reverse(LIST_URL_NAME), headers=auth)
    return len(queries)


def test_the_number_of_queries_does_not_grow_with_the_number_of_applications(
    client, auth, django_assert_max_num_queries
):
    _application_with_every_kind_of_answer()
    # The first request fills process-level caches; later ones are the steady state.
    client.get(reverse(LIST_URL_NAME), headers=auth)
    one_application = _query_count_of_list(client, auth)
    _application_with_every_kind_of_answer()
    _application_with_every_kind_of_answer()

    with django_assert_max_num_queries(QUERY_BOUND):
        three_applications = _query_count_of_list(client, auth)

    assert three_applications == one_application


def test_the_schema_describes_the_answer_entries(auth):
    document = APIClient().get(reverse("api:schema"), headers=auth).json()
    schemas = document["components"]["schemas"]

    answers = schemas["CourseApplicationApi"]["properties"]["answers"]
    answer = schemas["QuestionAnswerApi"]

    assert answers["items"] == {"$ref": "#/components/schemas/QuestionAnswerApi"}
    assert list(answer["properties"]) == EXPECTED_ANSWER_FIELDS
    assert answer["properties"]["value"]["oneOf"] == [
        {"type": "string", "nullable": True},
        {"type": "array", "items": {"type": "string"}, "nullable": True},
    ]
