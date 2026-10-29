"""Admin tests for the read-only course application changelist."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.accounts.models import User
from freedom_ls.course_applications.admin import (
    AnonymousApplicantAdmin,
    CourseApplicationAdmin,
)
from freedom_ls.course_applications.claims import update_applicant_email
from freedom_ls.course_applications.factories import (
    AnonymousApplicantFactory,
    CourseApplicationFactory,
)
from freedom_ls.course_applications.models import (
    AnonymousApplicant,
    CourseApplication,
)
from freedom_ls.course_applications.tests.helpers import (
    gated_course_with_form,
    unverified_application_with_file,
)
from freedom_ls.form_engine.factories import (
    FormProgressFactory,
    QuestionAnswerFactory,
    QuestionAnswerFileFactory,
)
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionAnswerFile,
)
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.site_context import site_context

pytestmark = pytest.mark.django_db

CHANGELIST = "admin:freedom_ls_course_applications_courseapplication_changelist"
ADD = "admin:freedom_ls_course_applications_courseapplication_add"
CHANGE = "admin:freedom_ls_course_applications_courseapplication_change"
DELETE = "admin:freedom_ls_course_applications_courseapplication_delete"
EXPORT = "admin:freedom_ls_course_applications_courseapplication_export"


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
    assert draft.applicant_email in content
    assert submitted.applicant_email in content


def test_is_submitted_column(mock_site_context):
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert model_admin.is_submitted(_draft()) is False
    assert model_admin.is_submitted(_submitted()) is True
    assert model_admin.is_submitted(CourseApplicationFactory()) is True


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
    assert application.user is not None

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
    assert application.user is not None
    staff = UserFactory(is_staff=True)
    staff.user_permissions.add(
        Permission.objects.get(codename="view_courseapplication")
    )
    client = Client()
    client.force_login(staff)

    content = client.get(reverse(CHANGE, args=[application.pk])).content.decode()

    assert application.applicant_email in content
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


def test_changelist_shows_an_anonymous_applications_email(staff_client):
    application = CourseApplicationFactory(anonymous=True)

    response = staff_client.get(reverse(CHANGELIST))

    assert response.status_code == 200
    assert application.anonymous_applicant.email in response.content.decode()


def test_change_page_shows_an_anonymous_applications_email(staff_client):
    application = CourseApplicationFactory(anonymous=True)

    response = staff_client.get(reverse(CHANGE, args=[application.pk]))

    assert response.status_code == 200
    assert application.anonymous_applicant.email in response.content.decode()


# ---------------------------------------------------------------------------
# Unverified applicants
# ---------------------------------------------------------------------------

APPLICANT_CHANGELIST = (
    "admin:freedom_ls_course_applications_anonymousapplicant_changelist"
)
APPLICANT_ADD = "admin:freedom_ls_course_applications_anonymousapplicant_add"
APPLICANT_DELETE = "admin:freedom_ls_course_applications_anonymousapplicant_delete"
FORM_PROGRESS_CHANGELIST = "admin:freedom_ls_form_engine_formprogress_changelist"
ANSWER_FILE_CHANGELIST = "admin:freedom_ls_form_engine_questionanswerfile_changelist"


def _admin_request(user: User):
    request = RequestFactory().get("/")
    request.user = user
    return request


def test_email_verified_column_is_false_for_an_anonymous_application(
    mock_site_context,
):
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert model_admin.is_email_verified(CourseApplicationFactory(anonymous=True)) is (
        False
    )


def test_email_verified_column_is_true_for_a_signed_in_application(
    mock_site_context,
):
    model_admin = CourseApplicationAdmin(CourseApplication, None)

    assert model_admin.is_email_verified(CourseApplicationFactory()) is True


def test_unverified_filter_narrows_to_anonymous_applications(staff_client):
    anonymous = CourseApplicationFactory(anonymous=True)
    CourseApplicationFactory()

    response = staff_client.get(reverse(CHANGELIST), {"email_verified": "unverified"})

    assert [row.pk for row in response.context["cl"].result_list] == [anonymous.pk]


def test_verified_filter_narrows_to_signed_in_applications(staff_client):
    CourseApplicationFactory(anonymous=True)
    verified = CourseApplicationFactory()

    response = staff_client.get(reverse(CHANGELIST), {"email_verified": "verified"})

    assert [row.pk for row in response.context["cl"].result_list] == [verified.pk]


def test_search_by_the_anonymous_email_finds_the_application(staff_client):
    wanted = CourseApplicationFactory(anonymous=True)
    CourseApplicationFactory(anonymous=True)

    response = staff_client.get(
        reverse(CHANGELIST), {"q": wanted.anonymous_applicant.email}
    )

    assert [row.pk for row in response.context["cl"].result_list] == [wanted.pk]


def test_change_page_summary_starts_with_the_unverified_email(staff_client):
    application = CourseApplicationFactory(anonymous=True)

    response = staff_client.get(reverse(CHANGE, args=[application.pk]))

    assert response.context["summary_rows"][0] == (
        "Unverified email",
        application.anonymous_applicant.email,
    )


def test_change_page_summary_of_a_signed_in_application_has_no_unverified_row(
    staff_client,
):
    application = CourseApplicationFactory()

    response = staff_client.get(reverse(CHANGE, args=[application.pk]))

    assert response.context["summary_rows"][0][0] == "Applicant"


def test_changelist_of_ten_anonymous_applications_stays_under_a_query_bound(
    staff_client, django_assert_max_num_queries
):
    for _ in range(10):
        CourseApplicationFactory(anonymous=True)

    with django_assert_max_num_queries(25):
        response = staff_client.get(reverse(CHANGELIST))

    assert response.status_code == 200


def test_applicant_admin_denies_add(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)

    request = _admin_request(UserFactory(superuser=True))

    assert model_admin.has_add_permission(request) is False


def test_applicant_admin_denies_change(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)
    applicant = AnonymousApplicantFactory()

    request = _admin_request(UserFactory(superuser=True))

    assert model_admin.has_change_permission(request, applicant) is False


def test_applicant_admin_allows_delete(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)
    applicant = AnonymousApplicantFactory()

    request = _admin_request(UserFactory(superuser=True))

    assert model_admin.has_delete_permission(request, applicant) is True


def test_applicant_admin_denies_delete_of_a_claimed_applicant(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)
    applicant = AnonymousApplicantFactory(user=UserFactory(), claimed_at=timezone.now())

    request = _admin_request(UserFactory(superuser=True))

    assert model_admin.has_delete_permission(request, applicant) is False


def _claimed(unverified):
    """Hand an unverified application to a user, the way a claim does."""
    user = UserFactory()
    unverified.application.user = user
    unverified.application.save()
    unverified.applicant.user = user
    unverified.applicant.claimed_at = timezone.now()
    unverified.applicant.save()
    unverified.sitting.user = user
    unverified.sitting.save()
    return unverified


def test_deleting_a_claimed_applicant_is_refused(staff_client):
    claimed = _claimed(unverified_application_with_file())
    url = reverse(APPLICANT_DELETE, args=[claimed.applicant.pk])

    response = staff_client.post(url, {"post": "yes"})

    assert response.status_code == 403


def test_deleting_a_claimed_applicant_leaves_the_users_application(staff_client):
    claimed = _claimed(unverified_application_with_file())
    url = reverse(APPLICANT_DELETE, args=[claimed.applicant.pk])

    staff_client.post(url, {"post": "yes"})

    assert CourseApplication.objects.filter(pk=claimed.application.pk).exists()


def test_bulk_delete_with_a_claimed_applicant_deletes_nothing(staff_client):
    unclaimed = unverified_application_with_file()
    claimed = _claimed(unverified_application_with_file())

    staff_client.post(
        reverse(APPLICANT_CHANGELIST),
        {
            "action": "delete_selected",
            "_selected_action": [
                str(unclaimed.applicant.pk),
                str(claimed.applicant.pk),
            ],
            "post": "yes",
        },
    )

    assert (
        CourseApplication.objects.filter(
            pk__in=[unclaimed.application.pk, claimed.application.pk]
        ).count()
        == 2
    )


def test_bulk_delete_confirmation_names_the_claimed_applicant_as_protected(
    staff_client,
):
    claimed = _claimed(unverified_application_with_file())

    response = staff_client.post(
        reverse(APPLICANT_CHANGELIST),
        {"action": "delete_selected", "_selected_action": [str(claimed.applicant.pk)]},
    )

    assert f"{claimed.applicant} (claimed)" in response.content.decode()


def test_deleting_an_applicant_keeps_their_address_out_of_the_admin_log(staff_client):
    unverified = unverified_application_with_file()
    url = reverse(APPLICANT_DELETE, args=[unverified.applicant.pk])

    staff_client.post(url, {"post": "yes"})

    entry = LogEntry.objects.get(object_id=str(unverified.applicant.pk))
    assert unverified.applicant.email not in entry.object_repr


def test_applicant_changelist_searches_by_email(staff_client):
    wanted = AnonymousApplicantFactory(email="findme@example.com")
    AnonymousApplicantFactory()

    response = staff_client.get(reverse(APPLICANT_CHANGELIST), {"q": "findme"})

    assert [row.pk for row in response.context["cl"].result_list] == [wanted.pk]


def test_applicant_admin_is_claimed_column_follows_claimed_at(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)
    claimed = AnonymousApplicantFactory(claimed_at=timezone.now())

    assert model_admin.is_claimed(claimed) is True


def test_applicant_admin_is_claimed_column_is_false_before_a_claim(mock_site_context):
    model_admin = AnonymousApplicantAdmin(AnonymousApplicant, None)

    assert model_admin.is_claimed(AnonymousApplicantFactory()) is False


def test_deleting_an_applicant_removes_the_application(staff_client):
    unverified = unverified_application_with_file()
    url = reverse(APPLICANT_DELETE, args=[unverified.applicant.pk])

    response = staff_client.post(url, {"post": "yes"})

    assert response.status_code == 302
    assert not CourseApplication.objects.filter(pk=unverified.application.pk).exists()


def test_deleting_an_applicant_removes_the_sitting_and_its_answers(staff_client):
    unverified = unverified_application_with_file()
    progress_pk = unverified.sitting.pk
    url = reverse(APPLICANT_DELETE, args=[unverified.applicant.pk])

    staff_client.post(url, {"post": "yes"})

    assert not FormProgress.objects.filter(pk=progress_pk).exists()
    assert not QuestionAnswer.objects.filter(form_progress_id=progress_pk).exists()


def test_deleting_an_applicant_removes_the_stored_file(staff_client):
    unverified = unverified_application_with_file()
    answer_file = QuestionAnswerFile.objects.get(
        answer__form_progress=unverified.sitting
    )
    storage, name = answer_file.file.storage, answer_file.file.name
    url = reverse(APPLICANT_DELETE, args=[unverified.applicant.pk])

    staff_client.post(url, {"post": "yes"})

    assert not storage.exists(name)


def test_delete_confirmation_page_loads_for_an_applicant_with_an_application(
    staff_client,
):
    unverified = unverified_application_with_file()
    url = reverse(APPLICANT_DELETE, args=[unverified.applicant.pk])

    response = staff_client.get(url)

    assert response.status_code == 200


def test_bulk_delete_removes_both_applicants_applications(staff_client):
    first = unverified_application_with_file()
    second = unverified_application_with_file()

    staff_client.post(
        reverse(APPLICANT_CHANGELIST),
        {
            "action": "delete_selected",
            "_selected_action": [
                str(first.applicant.pk),
                str(second.applicant.pk),
            ],
            "post": "yes",
        },
    )

    assert not CourseApplication.objects.filter(
        pk__in=[first.application.pk, second.application.pk]
    ).exists()


def test_bulk_delete_removes_both_applicants_sittings(staff_client):
    first = unverified_application_with_file()
    second = unverified_application_with_file()
    sitting_pks = [first.sitting.pk, second.sitting.pk]

    staff_client.post(
        reverse(APPLICANT_CHANGELIST),
        {
            "action": "delete_selected",
            "_selected_action": [
                str(first.applicant.pk),
                str(second.applicant.pk),
            ],
            "post": "yes",
        },
    )

    assert not FormProgress.objects.filter(pk__in=sitting_pks).exists()


def test_form_progress_changelist_labels_an_unverified_sitting(staff_client):
    unverified = unverified_application_with_file()

    response = staff_client.get(reverse(FORM_PROGRESS_CHANGELIST))

    assert f"Unverified: {unverified.applicant.email}" in response.content.decode()


def test_form_progress_changelist_of_ten_unverified_sittings_stays_under_a_query_bound(
    staff_client, django_assert_max_num_queries
):
    for _ in range(10):
        unverified_application_with_file()

    with django_assert_max_num_queries(25):
        response = staff_client.get(reverse(FORM_PROGRESS_CHANGELIST))

    assert response.status_code == 200


def test_form_progress_change_page_summary_has_the_unverified_email(staff_client):
    unverified = unverified_application_with_file()

    response = staff_client.get(_application_sitting_change_url(unverified.application))

    assert (
        "Unverified email",
        unverified.applicant.email,
    ) in response.context["summary_rows"]


def test_answer_file_changelist_labels_an_unverified_sitting(staff_client):
    unverified = unverified_application_with_file()

    response = staff_client.get(reverse(ANSWER_FILE_CHANGELIST))

    assert f"Unverified: {unverified.applicant.email}" in response.content.decode()


def test_answer_file_changelist_of_ten_unverified_files_stays_under_a_query_bound(
    staff_client, django_assert_max_num_queries
):
    for _ in range(10):
        unverified_application_with_file()

    with django_assert_max_num_queries(25):
        response = staff_client.get(reverse(ANSWER_FILE_CHANGELIST))

    assert response.status_code == 200


def test_erasing_a_claimed_applicants_user_removes_the_applicant_and_its_records(
    staff_client,
):
    user = UserFactory()
    unverified = unverified_application_with_file()
    applicant = unverified.applicant
    progress = unverified.sitting
    answer_file = QuestionAnswerFile.objects.get(answer__form_progress=progress)
    storage, name = answer_file.file.storage, answer_file.file.name
    application = unverified.application
    application.user = user
    application.save()
    applicant.user = user
    applicant.claimed_at = timezone.now()
    applicant.save()
    progress.user = user
    progress.save()

    response = staff_client.post(
        reverse("admin:freedom_ls_accounts_user_delete", args=[user.pk]),
        {"post": "yes"},
    )

    assert response.status_code == 302
    assert not AnonymousApplicant.objects.filter(pk=applicant.pk).exists()
    assert not CourseApplication.objects.filter(pk=unverified.application.pk).exists()
    assert not FormProgress.objects.filter(pk=progress.pk).exists()
    assert not storage.exists(name)


def test_changelist_shows_a_changed_address_as_unverified(staff_client):
    application = CourseApplicationFactory(anonymous=True)
    update_applicant_email(application.anonymous_applicant, "corrected@example.com")

    response = staff_client.get(reverse(CHANGELIST))

    row = response.context["cl"].result_list[0]
    assert (
        row.applicant_email,
        CourseApplicationAdmin(CourseApplication, None).is_email_verified(row),
    ) == ("corrected@example.com", False)


def test_changelist_offers_the_export_action_and_button(staff_client):
    response = staff_client.get(reverse(CHANGELIST))

    assert b"export_admin_action" in response.content
    assert reverse(EXPORT).encode() in response.content


def test_export_honours_the_course_filter(staff_client):
    wanted = CourseApplicationFactory()
    other = CourseApplicationFactory()

    response = staff_client.get(
        reverse(EXPORT), {"course__id__exact": wanted.course.pk}
    )

    body = response.content.decode("utf-8-sig")
    assert wanted.applicant_email in body
    assert other.applicant_email not in body


def test_export_honours_the_submitted_filter(staff_client):
    draft = _draft()
    submitted = _submitted()

    response = staff_client.get(reverse(EXPORT), {"submitted": "draft"})

    body = response.content.decode("utf-8-sig")
    assert draft.applicant_email in body
    assert submitted.applicant_email not in body


def test_export_returns_403_without_any_course_applications_permission(
    mock_site_context,
):
    client = Client()
    client.force_login(UserFactory(staff=True))

    assert client.get(reverse(EXPORT)).status_code == 403


def test_export_omits_a_user_held_application_on_another_site(staff_client, site):
    other_site = SiteFactory()
    with site_context(other_site):
        other = CourseApplicationFactory()

    response = staff_client.get(reverse(EXPORT))

    assert other.applicant_email not in response.content.decode("utf-8-sig")


def test_export_omits_an_anonymous_application_on_another_site(staff_client, site):
    other_site = SiteFactory()
    with site_context(other_site):
        other = CourseApplicationFactory(anonymous=True)

    response = staff_client.get(reverse(EXPORT))

    assert other.applicant_email not in response.content.decode("utf-8-sig")


def test_export_selected_carries_the_question_texts_and_an_answer(staff_client):
    course, form = gated_course_with_form()
    sitting = FormProgressFactory(form=form)
    application = CourseApplicationFactory(course=course, form_progress=sitting)
    question = FormQuestion.objects.get(form_page__form=form, question="Your name")
    QuestionAnswerFactory(
        form_progress=sitting, question=question, text_answer="Ada Lovelace"
    )

    response = staff_client.post(
        reverse(CHANGELIST),
        {
            "action": "export_admin_action",
            "select_across": "1",
            "index": "0",
            "_selected_action": [str(application.pk)],
        },
    )

    body = response.content.decode("utf-8-sig")
    assert "Your name" in body
    assert "Ada Lovelace" in body


def test_a_view_only_user_sees_on_the_change_page_the_answers_the_export_writes(
    mock_site_context,
):
    course, form = gated_course_with_form()
    sitting = FormProgressFactory(form=form)
    application = CourseApplicationFactory(course=course, form_progress=sitting)
    question = FormQuestion.objects.get(form_page__form=form, question="Your name")
    QuestionAnswerFactory(
        form_progress=sitting, question=question, text_answer="Ada Lovelace"
    )
    viewer = UserFactory(staff=True)
    viewer.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="freedom_ls_course_applications",
            codename="view_courseapplication",
        )
    )
    client = Client()
    client.force_login(viewer)

    response = client.get(reverse(CHANGE, args=[application.pk]))

    assert "Ada Lovelace" in response.content.decode()
