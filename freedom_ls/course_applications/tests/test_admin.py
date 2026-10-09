"""Admin tests for the read-only course application changelist."""

from __future__ import annotations

from datetime import UTC, datetime
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
from freedom_ls.course_applications.tests.helpers import gated_course_with_form
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    QuestionAnswerFile,
)

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
    assert draft.email in content
    assert submitted.email in content


def test_is_submitted_column(mock_site_context):
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert model_admin.is_submitted(_draft()) is False
    assert model_admin.is_submitted(_submitted()) is True
    assert model_admin.is_submitted(CourseApplicationFactory()) is True


def test_claimed_column_directly_follows_applicant_column(mock_site_context):
    """The Claimed column used to sit after Applicant name, not next to Applicant."""
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert list(model_admin.list_display[:3]) == [
        "applicant_email",
        "is_claimed",
        "applicant_name",
    ]


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
    application = CourseApplicationFactory(
        form_progress=FormProgressFactory(completed_time=timezone.now())
    )
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
        assert obj is not None
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

    assert application.email in content
    assert application.course.title in content
    assert str(application.form_progress) in content
    for name, obj in [
        ("freedom_ls_accounts_user_change", application.user),
        ("freedom_ls_content_engine_course_change", application.course),
        ("freedom_ls_form_engine_formprogress_change", application.form_progress),
    ]:
        assert obj is not None
        assert reverse(f"admin:{name}", args=[obj.pk]) not in content
    assert "id-scan.png" in content
    assert download_url not in content


def test_change_page_of_an_application_with_no_form_has_no_answers_section(
    staff_client,
):
    application = CourseApplicationFactory()

    content = staff_client.get(reverse(CHANGE, args=[application.pk])).content.decode()

    assert ">Answers<" not in content


def _application_sitting_change_url(application: CourseApplication) -> str:
    assert application.form_progress is not None
    return reverse(
        "admin:freedom_ls_form_engine_formprogress_change",
        args=[application.form_progress.pk],
    )


def test_form_progress_change_page_links_to_its_application(staff_client):
    application, _ = _answered_application()
    label = f"Application for {application.course.title}"

    content = staff_client.get(
        _application_sitting_change_url(application)
    ).content.decode()

    assert label in content
    assert f'href="{reverse(CHANGE, args=[application.pk])}"' in content


def test_form_progress_change_page_shows_application_as_text_without_view_permission(
    mock_site_context,
):
    application, _ = _answered_application()
    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename="view_formprogress"))
    client = Client()
    client.force_login(staff)

    content = client.get(_application_sitting_change_url(application)).content.decode()

    assert f"Application for {application.course.title}" in content
    assert reverse(CHANGE, args=[application.pk]) not in content


def test_submitted_filter_agrees_with_is_submitted(staff_client):
    draft = _draft()
    submitted = _submitted()
    no_form = CourseApplicationFactory()

    def listed(value: str) -> set[int]:
        response = staff_client.get(reverse(CHANGELIST), {"submitted": value})
        assert response.status_code == 200
        return {row.pk for row in response.context["cl"].result_list}

    assert listed("submitted") == {submitted.pk, no_form.pk}
    assert listed("draft") == {draft.pk}
    assert draft.is_submitted is False
    assert submitted.is_submitted is True
    assert no_form.is_submitted is True


def test_course_filter_returns_only_that_courses_applications(staff_client):
    wanted = CourseApplicationFactory()
    CourseApplicationFactory()

    response = staff_client.get(
        reverse(CHANGELIST), {"course__id__exact": wanted.course.pk}
    )

    assert [row.pk for row in response.context["cl"].result_list] == [wanted.pk]


def test_search_by_last_name_and_course_title(staff_client):
    application = CourseApplicationFactory(
        user=UserFactory(last_name="Zyxwvuts"),
        course=CourseApplicationFactory().course,
    )
    CourseApplicationFactory()

    for term in ("Zyxwvuts", application.course.title):
        response = staff_client.get(reverse(CHANGELIST), {"q": term})
        pks = {row.pk for row in response.context["cl"].result_list}
        assert application.pk in pks


def test_created_date_range_with_only_date_boxes_narrows_the_list(staff_client):
    old = CourseApplicationFactory()
    recent = CourseApplicationFactory()
    CourseApplication.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timezone.timedelta(days=30)
    )
    day = timezone.localdate(recent.created_at)

    response = staff_client.get(
        reverse(CHANGELIST),
        {"created_at_from_0": day.isoformat(), "created_at_to_0": day.isoformat()},
    )

    assert [row.pk for row in response.context["cl"].result_list] == [recent.pk]


def test_change_page_submitted_time_is_formatted_like_created_at(staff_client):
    application = _submitted()
    assert application.form_progress is not None
    application.form_progress.completed_time = datetime(
        2026, 10, 5, 19, 29, 6, 975164, tzinfo=UTC
    )
    application.form_progress.save()

    response = staff_client.get(reverse(CHANGE, args=[application.pk]))

    content = response.content.decode()
    assert "Oct. 5, 2026, 7:29 p.m." in content
    assert "19:29:06.975164" not in content


def test_created_date_range_with_blank_times_shows_no_time_errors(staff_client):
    """A date-only range used to flag both empty time boxes as "Enter a valid time."."""
    recent = CourseApplicationFactory()
    day = timezone.localdate(recent.created_at).isoformat()

    response = staff_client.get(
        reverse(CHANGELIST), {"created_at_from_0": day, "created_at_to_0": day}
    )

    assert "Enter a valid time." not in response.content.decode()


class TestUnclaimedRows:
    def test_unclaimed_row_lists_its_email(self, mock_site_context):
        app = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        assert CourseApplicationAdmin.applicant_email(None, app) == "pat@example.com"

    def test_unclaimed_row_shows_a_dash_for_the_name(self, mock_site_context):
        app = CourseApplicationFactory(unclaimed=True)

        assert CourseApplicationAdmin.applicant_name(None, app) == "-"


def _unclaimed_with_answers() -> tuple[CourseApplication, FormProgress, str]:
    """An unclaimed application whose sitting holds an answer and a stored file;
    returns it, the sitting and the stored file's name."""
    course, form = gated_course_with_form()
    progress = cast(FormProgress, FormProgressFactory(form=form, user=None))
    application = cast(
        CourseApplication,
        CourseApplicationFactory(unclaimed=True, course=course, form_progress=progress),
    )
    upload = FormQuestion.objects.get(form_page__form=form, type="file_upload")
    answer_file = QuestionAnswerFileFactory(
        answer=QuestionAnswerFactory(form_progress=progress, question=upload)
    )
    return application, progress, answer_file.file.name


def _staff_without_delete_permission() -> Client:
    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(codename="view_courseapplication")
    )
    client = Client()
    client.force_login(staff)
    return client


class TestUnclaimedAdmin:
    def test_unclaimed_row_is_listed_as_not_claimed(self, staff_client):
        application = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        response = staff_client.get(reverse(CHANGELIST))

        content = response.content.decode()
        assert "pat@example.com" in content
        assert CourseApplicationAdmin.is_claimed(None, application) is False

    def test_claimed_filter_separates_the_rows(self, staff_client):
        claimed = CourseApplicationFactory()
        unclaimed = CourseApplicationFactory(unclaimed=True)

        def listed(user_is_empty: str) -> set[int]:
            response = staff_client.get(
                reverse(CHANGELIST), {"user__isempty": user_is_empty}
            )
            return {row.pk for row in response.context["cl"].result_list}

        assert listed("0") == {claimed.pk}
        assert listed("1") == {unclaimed.pk}

    def test_search_by_typed_email(self, staff_client):
        wanted = CourseApplicationFactory(unclaimed=True, email="needle@example.com")
        CourseApplicationFactory(unclaimed=True, email="other@example.com")

        response = staff_client.get(reverse(CHANGELIST), {"q": "needle@example.com"})

        assert [row.pk for row in response.context["cl"].result_list] == [wanted.pk]

    def test_change_page_of_an_unclaimed_row_says_email_unverified(self, staff_client):
        application = CourseApplicationFactory(unclaimed=True, email="pat@example.com")

        content = staff_client.get(
            reverse(CHANGE, args=[application.pk])
        ).content.decode()

        assert "Unclaimed: email unverified" in content
        assert "pat@example.com" in content

    def test_delete_is_allowed_only_for_unclaimed(self, staff_client):
        unclaimed = CourseApplicationFactory(unclaimed=True)
        claimed = CourseApplicationFactory()

        assert staff_client.get(reverse(DELETE, args=[unclaimed.pk])).status_code == 200
        assert staff_client.get(reverse(DELETE, args=[claimed.pk])).status_code == 403

    def test_delete_is_refused_to_staff_without_the_delete_permission(
        self, mock_site_context
    ):
        application = CourseApplicationFactory(unclaimed=True)
        client = _staff_without_delete_permission()

        response = client.post(reverse(DELETE, args=[application.pk]), {"post": "yes"})

        assert response.status_code == 403
        assert CourseApplication.objects.filter(pk=application.pk).exists()

    def test_deleting_an_unclaimed_row_removes_its_sitting(self, staff_client):
        application, progress, _ = _unclaimed_with_answers()

        response = staff_client.post(
            reverse(DELETE, args=[application.pk]), {"post": "yes"}
        )

        assert response.status_code == 302
        assert not CourseApplication.objects.filter(pk=application.pk).exists()
        assert not FormProgress.objects.filter(pk=progress.pk).exists()

    def test_deleting_an_unclaimed_row_removes_its_stored_files(self, staff_client):
        application, _, file_name = _unclaimed_with_answers()
        storage = QuestionAnswerFile._meta.get_field("file").storage
        assert storage.exists(file_name)

        staff_client.post(reverse(DELETE, args=[application.pk]), {"post": "yes"})

        assert not storage.exists(file_name)

    def test_delete_confirmation_lists_the_sitting(self, staff_client):
        application, progress, _ = _unclaimed_with_answers()

        content = staff_client.get(
            reverse(DELETE, args=[application.pk])
        ).content.decode()

        assert "Form progress" in content
        assert str(progress) in content

    def test_delete_selected_action_is_absent(self, staff_client):
        CourseApplicationFactory(unclaimed=True)

        response = staff_client.get(reverse(CHANGELIST))

        assert "delete_selected" not in response.content.decode()
