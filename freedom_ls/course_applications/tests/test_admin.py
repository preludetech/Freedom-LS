"""Admin tests for the read-only course application changelist."""

from __future__ import annotations

from typing import cast

import pytest

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.course_applications.admin import CourseApplicationAdmin
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import CourseApplication
from freedom_ls.course_applications.tests.conftest import gated_course_with_form
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import FormProgress, FormQuestion

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:freedom_ls_course_applications_courseapplication_changelist"
ADD = "admin:freedom_ls_course_applications_courseapplication_add"
CHANGE = "admin:freedom_ls_course_applications_courseapplication_change"
DELETE = "admin:freedom_ls_course_applications_courseapplication_delete"


def _draft() -> CourseApplication:
    return cast(
        CourseApplication,
        CourseApplicationFactory(form_progress=FormProgressFactory()),
    )


def _submitted() -> CourseApplication:
    return cast(
        CourseApplication,
        CourseApplicationFactory(
            form_progress=FormProgressFactory(completed_time=timezone.now())
        ),
    )


def test_changelist_lists_drafts_and_submitted(staff_client):
    draft = _draft()
    submitted = _submitted()

    response = staff_client.get(reverse(CHANGELIST))

    assert response.status_code == 200
    content = response.content.decode()
    assert draft.user.email in content
    assert submitted.user.email in content


def test_is_submitted_column(mock_site_context):
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert model_admin.is_submitted(_draft()) is False
    assert model_admin.is_submitted(_submitted()) is True
    assert model_admin.is_submitted(CourseApplicationFactory()) is True


def test_submitted_time_is_sitting_completed_time(mock_site_context):
    model_admin = CourseApplicationAdmin(CourseApplication, None)
    submitted = _submitted()
    no_form = CourseApplicationFactory()

    assert submitted.form_progress is not None
    assert model_admin.submitted_time(submitted) == (
        submitted.form_progress.completed_time
    )
    assert model_admin.submitted_time(no_form) == no_form.created_at
    assert model_admin.submitted_time(_draft()) is None


def test_add_view_is_forbidden(staff_client):
    assert staff_client.get(reverse(ADD)).status_code == 403


def test_delete_view_is_forbidden_and_row_remains(staff_client):
    application = _submitted()
    url = reverse(DELETE, args=[application.pk])

    assert staff_client.get(url).status_code == 403
    assert staff_client.post(url, {"post": "yes"}).status_code == 403
    assert CourseApplication.objects.filter(pk=application.pk).exists()


def test_change_page_is_view_only(staff_client):
    application = _submitted()
    url = reverse(CHANGE, args=[application.pk])

    response = staff_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="_save"' not in content
    assert 'name="_continue"' not in content
    assert staff_client.post(url, {}).status_code == 403


def test_deleting_applicant_removes_application_and_sitting(staff_client):
    user = UserFactory()
    application = CourseApplicationFactory(
        user=user,
        form_progress=FormProgressFactory(user=user, completed_time=timezone.now()),
    )
    progress_pk = application.form_progress.pk
    url = reverse("admin:freedom_ls_accounts_user_delete", args=[user.pk])

    response = staff_client.post(url, {"post": "yes"})

    assert response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
    assert not CourseApplication.objects.filter(pk=application.pk).exists()
    assert not FormProgress.objects.filter(pk=progress_pk).exists()


def test_staff_with_view_permission_can_open_changelist(mock_site_context):
    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(codename="view_courseapplication")
    )
    client = Client()
    client.force_login(staff)

    assert client.get(reverse(CHANGELIST)).status_code == 200


def test_staff_without_view_permission_cannot_open_changelist(mock_site_context):
    client = Client()
    client.force_login(UserFactory(is_staff=True))

    assert client.get(reverse(CHANGELIST)).status_code == 403


def _answered_application() -> tuple[CourseApplication, str]:
    """A submitted application with one text answer, one skipped question and
    one uploaded file; returns it and the file's download URL."""
    course, form = gated_course_with_form()
    progress = FormProgressFactory(form=form, completed_time=timezone.now())
    application = cast(
        CourseApplication,
        CourseApplicationFactory(
            user=progress.user, course=course, form_progress=progress
        ),
    )
    name = FormQuestion.objects.get(form_page__form=form, question="Your name")
    QuestionAnswerFactory(
        form_progress=progress, question=name, text_answer="Ada Lovelace"
    )
    upload = FormQuestion.objects.get(form_page__form=form, type="file_upload")
    answer_file = QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=progress, question=upload),
        original_filename="id-scan.png",
    )
    download_url = reverse(
        "admin:freedom_ls_form_engine_questionanswerfile_download",
        args=[answer_file.pk],
    )
    return application, download_url


def test_change_page_shows_the_answers_document(staff_client):
    application, _ = _answered_application()

    response = staff_client.get(reverse(CHANGE, args=[application.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "About you" in content
    assert "Supporting documents" in content
    assert "Ada Lovelace" in content
    assert "Not answered" in content
    assert "id-scan.png" in content


def test_change_page_summary_links_to_user_course_and_sitting(staff_client):
    application, _ = _answered_application()
    assert application.form_progress is not None

    content = staff_client.get(reverse(CHANGE, args=[application.pk])).content.decode()

    for name, obj in [
        ("freedom_ls_accounts_user_change", application.user),
        ("freedom_ls_content_engine_course_change", application.course),
        ("freedom_ls_form_engine_formprogress_change", application.form_progress),
    ]:
        assert f'href="{reverse(f"admin:{name}", args=[obj.pk])}"' in content


def test_change_page_summary_is_plain_text_for_a_reader_who_cannot_open_the_links(
    mock_site_context,
):
    application, download_url = _answered_application()
    assert application.form_progress is not None
    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(codename="view_courseapplication")
    )
    client = Client()
    client.force_login(staff)

    content = client.get(reverse(CHANGE, args=[application.pk])).content.decode()

    assert application.user.email in content
    assert application.course.title in content
    assert str(application.form_progress) in content
    for name, obj in [
        ("freedom_ls_accounts_user_change", application.user),
        ("freedom_ls_content_engine_course_change", application.course),
        ("freedom_ls_form_engine_formprogress_change", application.form_progress),
    ]:
        assert reverse(f"admin:{name}", args=[obj.pk]) not in content
    assert "id-scan.png" in content
    assert download_url not in content


def test_change_page_of_an_application_with_no_form_says_so(staff_client):
    application = CourseApplicationFactory()

    content = staff_client.get(reverse(CHANGE, args=[application.pk])).content.decode()

    assert "The course asked for no application form." in content
    assert ">Answers<" not in content
