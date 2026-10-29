"""Tests for the CSV export on the course application admin."""

from __future__ import annotations

import csv
import io
from typing import cast

import pytest

from django.contrib.auth.models import Permission
from django.db import connection
from django.http import HttpResponse
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.resources import (
    APPLICATION_EXPORT_FIELDS,
    CourseApplicationResource,
)
from freedom_ls.course_applications.tests.helpers import gated_course_with_form
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormQuestion

pytestmark = pytest.mark.django_db

APP_LABEL = "freedom_ls_course_applications"


@pytest.fixture
def staff_client(mock_site_context, db):
    """Staff user with permission to view course applications."""
    user = UserFactory(staff=True)
    permission = Permission.objects.get(
        content_type__app_label=APP_LABEL, codename="view_courseapplication"
    )
    user.user_permissions.add(permission)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def unprivileged_staff_client(mock_site_context, db):
    """Staff user with no permission on any course applications model."""
    user = UserFactory(staff=True)
    client = Client()
    client.force_login(user)
    return client


def _export_selected(
    client: Client, model_name: str, pks: list[str], query: str = ""
) -> HttpResponse:
    response: HttpResponse = client.post(
        reverse(f"admin:{APP_LABEL}_{model_name}_changelist") + query,
        {
            "action": "export_admin_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": pks,
        },
    )
    return response


def _rows(response: HttpResponse) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    return rows[0], rows[1:]


def _export_row(client: Client, application: CourseApplication) -> dict[str, str]:
    """The row exported for `application`, keyed by column name."""
    response = _export_selected(client, "courseapplication", [str(application.pk)])
    header, rows = _rows(response)
    (row,) = rows
    return dict(zip(header, row, strict=True))


def test_export_header_is_the_fixed_columns_in_order(staff_client):
    application = CourseApplicationFactory()

    response = _export_selected(
        staff_client, "courseapplication", [str(application.pk)]
    )

    header, _ = _rows(response)
    assert header == list(APPLICATION_EXPORT_FIELDS)


def test_a_user_held_application_writes_the_users_details(staff_client):
    application = CourseApplicationFactory(
        user=UserFactory(first_name="Ada", last_name="Lovelace")
    )

    row = _export_row(staff_client, application)

    assert row["id"] == str(application.pk)
    assert row["applicant_email"] == application.user.email
    assert row["applicant_name"] == "Ada Lovelace"
    assert row["is_email_verified"] == "TRUE"
    assert row["course"] == application.course.title


def test_an_unclaimed_anonymous_application_writes_the_applicants_details(
    staff_client,
):
    application = CourseApplicationFactory(anonymous=True)

    row = _export_row(staff_client, application)

    assert row["applicant_email"] == application.anonymous_applicant.email
    assert row["applicant_name"] == "Anna Applicant"
    assert row["is_email_verified"] == "FALSE"


def test_a_draft_is_not_submitted_and_has_no_submitted_time(staff_client):
    application = CourseApplicationFactory(anonymous_draft=True)

    row = _export_row(staff_client, application)

    assert row["is_submitted"] == "FALSE"
    assert row["submitted_time"] == ""


def test_an_application_with_no_sitting_was_submitted_when_it_was_created(
    staff_client,
):
    application = CourseApplicationFactory()

    row = _export_row(staff_client, application)

    assert row["is_submitted"] == "TRUE"
    assert row["submitted_time"] == application.created_at.isoformat()


def test_a_completed_sitting_writes_its_completed_time(staff_client):
    completed_time = timezone.now()
    application = cast(
        CourseApplication,
        CourseApplicationFactory(
            form_progress=FormProgressFactory(completed_time=completed_time)
        ),
    )

    row = _export_row(staff_client, application)

    assert row["is_submitted"] == "TRUE"
    assert row["submitted_time"] == completed_time.isoformat()


def _form_questions(form: Form) -> list[FormQuestion]:
    return list(
        FormQuestion.objects.filter(form_page__form=form).order_by(
            "form_page__order", "order"
        )
    )


def _application_for(course, form, **sitting_fields) -> CourseApplication:
    sitting: FormProgress = FormProgressFactory(form=form, **sitting_fields)
    return cast(
        CourseApplication,
        CourseApplicationFactory(course=course, form_progress=sitting),
    )


def _answer(application: CourseApplication, question: FormQuestion, **fields):
    return QuestionAnswerFactory(
        form_progress=application.form_progress, question=question, **fields
    )


def test_export_header_adds_the_forms_question_texts_after_the_fixed_columns(
    staff_client,
):
    course, form = gated_course_with_form()
    application = _application_for(course, form)

    response = _export_selected(
        staff_client, "courseapplication", [str(application.pk)]
    )

    header, _ = _rows(response)
    assert header == [
        *APPLICATION_EXPORT_FIELDS,
        "Your name",
        "Years of experience",
        "How did you hear about us",
        "Why apply",
        "Upload your ID",
    ]


def test_a_skipped_question_has_an_empty_cell_beside_the_answered_ones(staff_client):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    name, years, choice, why, _upload = _form_questions(form)
    _answer(application, name, text_answer="Ada")
    _answer(application, years, text_answer="12")
    _answer(application, why, text_answer="Because")
    _answer(application, choice).selected_options.add(choice.options.get(order=1))

    row = _export_row(staff_client, application)

    assert [
        row["Your name"],
        row["Years of experience"],
        row["How did you hear about us"],
        row["Why apply"],
        row["Upload your ID"],
    ] == ["Ada", "12", "Search", "Because", ""]


def test_an_application_with_no_sitting_has_empty_answer_cells(staff_client):
    course, form = gated_course_with_form()
    answered = _application_for(course, form)
    _answer(answered, _form_questions(form)[0], text_answer="Ada")
    bare = CourseApplicationFactory(course=course)

    response = _export_selected(
        staff_client, "courseapplication", [str(answered.pk), str(bare.pk)]
    )

    header, rows = _rows(response)
    bare_row = next(
        dict(zip(header, row, strict=True)) for row in rows if row[0] == str(bare.pk)
    )
    assert [bare_row[question.question] for question in _form_questions(form)] == [
        ""
    ] * 5


def test_an_answer_starting_with_a_formula_trigger_is_escaped(staff_client):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    _answer(application, _form_questions(form)[0], text_answer="=1+1")

    row = _export_row(staff_client, application)

    assert row["Your name"] == "'=1+1"


def test_a_question_text_starting_with_a_formula_trigger_has_its_header_escaped(
    staff_client,
):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    question = _form_questions(form)[0]
    question.question = "=SUM(A1)"
    question.save(update_fields=["question"])

    response = _export_selected(
        staff_client, "courseapplication", [str(application.pk)]
    )

    header, _ = _rows(response)
    assert "'=SUM(A1)" in header


def test_a_file_answer_exports_its_original_filename_and_no_storage_detail(
    staff_client,
):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    answer = _answer(application, _form_questions(form)[-1])
    stored = QuestionAnswerFileFactory(answer=answer, original_filename="id-scan.png")

    response = _export_selected(
        staff_client, "courseapplication", [str(application.pk)]
    )

    header, rows = _rows(response)
    assert dict(zip(header, rows[0], strict=True))["Upload your ID"] == "id-scan.png"
    body = response.content.decode("utf-8-sig")
    assert stored.file.name not in body
    assert "http" not in body


def test_a_reworded_question_keeps_one_column_holding_the_earlier_answer(
    staff_client,
):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    question = _form_questions(form)[0]
    _answer(application, question, text_answer="Ada")
    question.question = "Your full name"
    question.save(update_fields=["question"])

    response = _export_selected(
        staff_client, "courseapplication", [str(application.pk)]
    )

    header, rows = _rows(response)
    assert header.count("Your full name") == 1
    assert "Your name" not in header
    assert dict(zip(header, rows[0], strict=True))["Your full name"] == "Ada"


def test_a_question_titled_like_a_fixed_column_keeps_its_own_column(staff_client):
    course, form = gated_course_with_form()
    application = _application_for(course, form)
    question = _form_questions(form)[0]
    question.question = "course"
    question.save(update_fields=["question"])
    _answer(application, question, text_answer="Ada")

    row = _export_row(staff_client, application)

    assert row["course"] == course.title
    assert row[f"course ({form.title})"] == "Ada"


def _answered_application(course, form) -> CourseApplication:
    application = _application_for(course, form, completed_time=timezone.now())
    name, years, choice, why, upload = _form_questions(form)
    _answer(application, name, text_answer="Ada")
    _answer(application, years, text_answer="12")
    _answer(application, choice).selected_options.add(choice.options.get(order=0))
    _answer(application, why, text_answer="Because")
    QuestionAnswerFileFactory(answer=_answer(application, upload))
    return application


def test_export_query_count_does_not_grow_with_the_number_of_applications(
    mock_site_context, django_assert_max_num_queries
):
    course, form = gated_course_with_form()
    for _ in range(2):
        _answered_application(course, form)
    with CaptureQueriesContext(connection) as captured:
        CourseApplicationResource().export(CourseApplication.objects.all())
    for _ in range(8):
        _answered_application(course, form)

    with django_assert_max_num_queries(len(captured)):
        CourseApplicationResource().export(CourseApplication.objects.all())


def test_applications_to_two_courses_leave_the_other_forms_columns_empty(
    staff_client,
):
    first_course, first_form = gated_course_with_form()
    second_form = FormFactory(title="Zeta form")
    FormQuestionFactory(
        form_page=FormPageFactory(form=second_form),
        type="short_text",
        question="Favourite colour",
    )
    second_course = CourseFactory(access_config={"access_type": "application_gated"})
    second_course.application_form = second_form
    second_course.save(update_fields=["application_form"])
    first = _application_for(first_course, first_form)
    second = _application_for(second_course, second_form)
    _answer(first, _form_questions(first_form)[0], text_answer="Ada")
    _answer(second, _form_questions(second_form)[0], text_answer="Green")

    response = _export_selected(
        staff_client, "courseapplication", [str(first.pk), str(second.pk)]
    )

    header, rows = _rows(response)
    by_id = {row[0]: dict(zip(header, row, strict=True)) for row in rows}
    assert "Favourite colour" in header
    assert "Your name" in header
    assert by_id[str(first.pk)]["Your name"] == "Ada"
    assert by_id[str(first.pk)]["Favourite colour"] == ""
    assert by_id[str(second.pk)]["Your name"] == ""
    assert by_id[str(second.pk)]["Favourite colour"] == "Green"
