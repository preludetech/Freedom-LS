"""Tests for the CSV export on the course application admin."""

from __future__ import annotations

import csv
import io
from typing import cast

import pytest

from django.contrib.auth.models import Permission
from django.http import HttpResponse
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.resources import APPLICATION_EXPORT_FIELDS
from freedom_ls.form_engine.factories import FormProgressFactory

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
