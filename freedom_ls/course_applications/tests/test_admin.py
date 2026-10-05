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
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import FormProgress

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
