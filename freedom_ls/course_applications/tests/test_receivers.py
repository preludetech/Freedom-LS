"""Tests for what signing in does to the session's anonymous applications."""

from __future__ import annotations

import pytest

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import QueryDict
from django.urls import reverse

from freedom_ls.accounts.factories import (
    EmailAddressFactory,
    UserFactory,
)
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.tests.images import png_bytes

if app_not_installed("freedom_ls.course_applications"):
    pytest.skip("course_applications not installed", allow_module_level=True)

from freedom_ls.course_applications.anonymous_session import (
    ANONYMOUS_APPLICANTS_SESSION_KEY,
)
from freedom_ls.course_applications.factories import CourseApplicationFactory
from freedom_ls.course_applications.models import AnonymousApplicant, CourseApplication
from freedom_ls.form_engine.factories import FormProgressFactory
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    QuestionAnswerFile,
    QuestionOption,
)
from freedom_ls.form_engine.session_access import ANONYMOUS_FORM_PROGRESS_SESSION_KEY

from .helpers import (
    application_ids_updated_since,
    gated_course_with_form,
    unverified_application_with_file,
)

pytestmark = pytest.mark.django_db


def _start_anonymous_draft(client, email: str) -> CourseApplication:
    course, _form = gated_course_with_form()
    client.post(
        reverse(
            "course_applications:applicant_details",
            kwargs={"course_slug": course.slug},
        ),
        {"email": email, "first_name": "Ada", "last_name": "Lovelace"},
    )
    application: CourseApplication = CourseApplication.objects.get(course=course)
    return application


def _page_one(application: CourseApplication) -> str:
    return reverse(
        "course_applications:form_page",
        kwargs={"pk": application.pk, "page_number": 1},
    )


def test_signing_in_to_the_verified_address_adopts_the_draft(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    application.refresh_from_db()
    sitting = FormProgress.objects.get(course_application=application)
    assert (application.user, sitting.user) == (user, user)


def test_an_adopted_draft_stays_reachable_after_signing_in(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    assert client.get(_page_one(application)).status_code == 200


def test_an_adopted_applicant_is_marked_claimed(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    applicant = AnonymousApplicant.objects.get(course_application=application)
    assert (applicant.user, applicant.claimed_at is not None) == (user, True)


def test_signing_in_to_a_mixed_case_verified_address_adopts_the_draft(
    client, mock_site_context
):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="Ada@Example.com")
    EmailAddressFactory(user=user, email="Ada@Example.com")

    client.force_login(user)

    application.refresh_from_db()
    assert application.user == user


def test_signing_in_drops_a_draft_for_a_course_the_account_already_applied_to(
    client, mock_site_context
):
    """The account's submission stays; the anonymous draft could only repeat
    it, so it is erased with its applicant and sitting rather than adopted."""
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)
    held = CourseApplicationFactory(user=user, course=application.course)

    client.force_login(user)

    assert list(CourseApplication.objects.filter(course=application.course)) == [held]
    assert not AnonymousApplicant.objects.filter(email="ada@example.com").exists()
    assert FormProgress.objects.count() == 0


def test_signing_in_over_a_held_submission_says_that_application_was_kept(
    client, mock_site_context
):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)
    CourseApplicationFactory(user=user, course=application.course)

    _sign_in(client, user)

    assert _application_messages(client) == [
        f"You had already applied for {application.course.title}, "
        "so that application was kept."
    ]


def _sign_in(client, user) -> None:
    """Sign in through the login form, the only path with a messages storage."""
    client.post(reverse("account_login"), {"login": user.email, "password": user.email})


def _application_messages(client) -> list[str]:
    """The pending messages about applications, leaving out the sign-in one."""
    return [
        str(m)
        for m in get_messages(client.get("/").wsgi_request)
        if "application" in str(m)
    ]


def _held_draft_and_signed_in_client(client):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)
    held = CourseApplicationFactory(
        user=user,
        course=application.course,
        form_progress=FormProgressFactory(user=user, completed_time=None),
    )
    _sign_in(client, user)
    return application, held


def test_signing_in_with_a_held_draft_adopts_the_incoming_draft(
    client, mock_site_context
):
    application, held = _held_draft_and_signed_in_client(client)

    application.refresh_from_db()
    assert (
        application.user,
        CourseApplication.objects.filter(pk=held.pk).exists(),
    ) == (held.user, False)


def test_signing_in_with_a_held_draft_deletes_the_held_sitting(
    client, mock_site_context
):
    _application, held = _held_draft_and_signed_in_client(client)

    assert not FormProgress.objects.filter(pk=held.form_progress_id).exists()


def test_signing_in_with_a_held_draft_says_it_was_replaced(client, mock_site_context):
    application, _held = _held_draft_and_signed_in_client(client)

    assert _application_messages(client) == [
        f"Your unfinished application for {application.course.title} "
        "was replaced by the one you just started."
    ]


def test_signing_in_to_adopt_a_draft_with_nothing_held_says_nothing(
    client, mock_site_context
):
    _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)

    _sign_in(client, user)

    assert _application_messages(client) == []


def test_signing_in_to_an_unverified_address_adopts_nothing(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user, verified=False)

    client.force_login(user)

    application.refresh_from_db()
    assert application.user is None


def test_signing_in_to_another_address_adopts_nothing(client, mock_site_context):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    application.refresh_from_db()
    assert application.user is None


def test_a_draft_under_another_address_is_out_of_reach_after_signing_in(
    client, mock_site_context
):
    application = _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")
    EmailAddressFactory(user=user)

    client.force_login(user)

    assert client.get(_page_one(application)).status_code == 404


def test_signing_in_empties_both_session_lists(client, mock_site_context):
    _start_anonymous_draft(client, "ada@example.com")
    user = UserFactory(email="bob@example.com")

    client.force_login(user)

    assert (
        client.session.get(ANONYMOUS_APPLICANTS_SESSION_KEY),
        client.session.get(ANONYMOUS_FORM_PROGRESS_SESSION_KEY),
    ) == ({}, [])


def test_deleting_a_course_removes_an_unclaimed_applicants_sitting(mock_site_context):
    """Nothing would name the sitting afterwards, so no erasure could reach it."""
    unverified = unverified_application_with_file()

    unverified.application.course.delete()

    assert not FormProgress.objects.filter(pk=unverified.sitting.pk).exists()


def test_deleting_a_course_removes_an_unclaimed_applicants_stored_file(
    mock_site_context,
):
    unverified = unverified_application_with_file()
    answer_file = QuestionAnswerFile.objects.get(
        answer__form_progress=unverified.sitting
    )
    storage, name = answer_file.file.storage, answer_file.file.name

    unverified.application.course.delete()

    assert not storage.exists(name)


def test_deleting_a_course_keeps_a_signed_in_applicants_sitting(mock_site_context):
    """A sitting with a user is still reachable through that user."""
    user = UserFactory()
    application = CourseApplicationFactory(
        user=user, form_progress=FormProgressFactory(user=user)
    )

    application.course.delete()

    assert FormProgress.objects.filter(pk=application.form_progress.pk).exists()


def _unclaimed_application_for(email: str, site=None):
    unverified = unverified_application_with_file()
    unverified.applicant.email = email
    if site is not None:
        unverified.applicant.site = site
    unverified.applicant.save()
    return unverified


def test_deleting_a_user_erases_their_unclaimed_applications(mock_site_context):
    user = UserFactory(email="ada@example.com")
    unverified = _unclaimed_application_for("ada@example.com")

    user.delete()

    assert not CourseApplication.objects.filter(pk=unverified.application.pk).exists()


def test_deleting_a_user_removes_their_unclaimed_applications_files(mock_site_context):
    user = UserFactory(email="ada@example.com")
    unverified = _unclaimed_application_for("ada@example.com")
    answer_file = QuestionAnswerFile.objects.get(
        answer__form_progress=unverified.sitting
    )
    storage, name = answer_file.file.storage, answer_file.file.name

    user.delete()

    assert not storage.exists(name)


def test_deleting_a_user_matches_their_address_regardless_of_case(mock_site_context):
    user = UserFactory(email="Ada@Example.com")
    unverified = _unclaimed_application_for("ada@example.com")

    user.delete()

    assert not AnonymousApplicant.objects.filter(pk=unverified.applicant.pk).exists()


def test_deleting_a_user_leaves_another_sites_applicant_with_that_address(
    mock_site_context,
):
    user = UserFactory(email="ada@example.com")
    elsewhere = _unclaimed_application_for("ada@example.com", site=SiteFactory())

    user.delete()

    assert AnonymousApplicant._base_manager.filter(pk=elsewhere.applicant.pk).exists()


def test_deleting_a_user_leaves_another_addresses_applicant(mock_site_context):
    user = UserFactory(email="ada@example.com")
    other = _unclaimed_application_for("bob@example.com")

    user.delete()

    assert AnonymousApplicant.objects.filter(pk=other.applicant.pk).exists()


def test_signing_in_with_a_held_draft_and_a_submitted_session_application_says_submitted(
    client, mock_site_context
):
    course = CourseFactory(access_config={"access_type": "application_gated"})
    client.post(
        reverse(
            "course_applications:applicant_details",
            kwargs={"course_slug": course.slug},
        ),
        {"email": "ada@example.com", "first_name": "Ada", "last_name": "Lovelace"},
    )
    client.post(
        reverse("course_applications:apply", kwargs={"course_slug": course.slug})
    )
    user = UserFactory(email="ada@example.com")
    EmailAddressFactory(user=user)
    CourseApplicationFactory(
        user=user,
        course=course,
        form_progress=FormProgressFactory(user=user, completed_time=None),
    )

    _sign_in(client, user)

    assert _application_messages(client) == [
        f"Your unfinished application for {course.title} "
        "was replaced by the one you just submitted."
    ]


@pytest.fixture
def draft(client, mock_site_context) -> CourseApplication:
    """An anonymous applicant's draft, started through the real apply flow."""
    return _start_anonymous_draft(client, "ada@example.com")


def _question(application: CourseApplication, question_type: str) -> FormQuestion:
    question: FormQuestion = FormQuestion.objects.get(
        form_page__form=application.course.application_form, type=question_type
    )
    return question


def _sitting(application: CourseApplication) -> FormProgress:
    assert application.form_progress is not None
    return application.form_progress


def _answer(application: CourseApplication, question: FormQuestion, *values: str):
    """Save `values` as the answer to `question` the way a page submission does."""
    post_data = QueryDict(mutable=True)
    post_data.setlist(f"question_{question.id}", list(values))
    _sitting(application).save_answers([question], post_data)


def _file_url(name: str, application: CourseApplication) -> str:
    return reverse(
        f"form_engine:{name}",
        kwargs={
            "progress_pk": _sitting(application).pk,
            "question_pk": _question(application, "file_upload").pk,
        },
    )


def _upload(client, application: CourseApplication) -> None:
    client.post(
        _file_url("question_file_upload", application),
        {"file": SimpleUploadedFile("id-scan.png", png_bytes())},
    )


def _updated_at(application: CourseApplication):
    application.refresh_from_db()
    return application.updated_at


def test_completing_the_sitting_moves_updated_at(draft):
    before = draft.updated_at

    draft.form_progress.complete()

    assert _updated_at(draft) > before


def test_completing_the_sitting_puts_the_application_in_an_updated_since_poll(
    draft, auth
):
    before = draft.updated_at

    draft.form_progress.complete()

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_saving_a_text_answer_moves_updated_at(draft):
    before = draft.updated_at

    _answer(draft, _question(draft, "short_text"), "Ada")

    assert _updated_at(draft) > before


def test_saving_a_text_answer_puts_the_application_in_an_updated_since_poll(
    draft, auth
):
    before = draft.updated_at

    _answer(draft, _question(draft, "short_text"), "Ada")

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_saving_an_option_answer_moves_updated_at(draft):
    question = _question(draft, "multiple_choice")
    option = QuestionOption.objects.get(question=question, order=0)
    before = draft.updated_at

    _answer(draft, question, str(option.pk))

    assert _updated_at(draft) > before


def test_saving_an_option_answer_puts_the_application_in_an_updated_since_poll(
    draft, auth
):
    question = _question(draft, "multiple_choice")
    option = QuestionOption.objects.get(question=question, order=0)
    before = draft.updated_at

    _answer(draft, question, str(option.pk))

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_clearing_an_answer_moves_updated_at(draft):
    question = _question(draft, "short_text")
    _answer(draft, question, "Ada")
    before = _updated_at(draft)

    _answer(draft, question, "")

    assert _updated_at(draft) > before


def test_clearing_an_answer_puts_the_application_in_an_updated_since_poll(draft, auth):
    question = _question(draft, "short_text")
    _answer(draft, question, "Ada")
    before = _updated_at(draft)

    _answer(draft, question, "")

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_uploading_a_file_moves_updated_at(client, draft):
    before = draft.updated_at

    _upload(client, draft)

    assert _updated_at(draft) > before


def test_uploading_a_file_puts_the_application_in_an_updated_since_poll(
    client, draft, auth
):
    before = draft.updated_at

    _upload(client, draft)

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_replacing_a_file_moves_updated_at(client, draft):
    _upload(client, draft)
    before = _updated_at(draft)

    _upload(client, draft)

    assert _updated_at(draft) > before


def test_replacing_a_file_puts_the_application_in_an_updated_since_poll(
    client, draft, auth
):
    _upload(client, draft)
    before = _updated_at(draft)

    _upload(client, draft)

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]


def test_removing_a_file_moves_updated_at(client, draft):
    _upload(client, draft)
    before = _updated_at(draft)

    client.post(_file_url("question_file_remove", draft))

    assert _updated_at(draft) > before


def test_removing_a_file_puts_the_application_in_an_updated_since_poll(
    client, draft, auth
):
    _upload(client, draft)
    before = _updated_at(draft)

    client.post(_file_url("question_file_remove", draft))

    assert application_ids_updated_since(auth, before) == [str(draft.pk)]
