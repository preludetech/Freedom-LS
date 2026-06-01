"""Batch 8 tests: views + helpers for stale-attempt safety net, runner context, form_submit_and_exit."""

from __future__ import annotations

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    ContentCollectionItemFactory,
    CourseFactory,
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.student_management.factories import UserCourseRegistrationFactory
from freedom_ls.student_progress.factories import FormProgressFactory
from freedom_ls.student_progress.models import FormProgress

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_course_with_form(form, *, title="Test Course"):
    """Create a course containing a single form as its only item."""
    course = CourseFactory(title=title)
    ContentCollectionItemFactory(collection_object=course, child_object=form)
    return course


def _register(user, course):
    UserCourseRegistrationFactory(user=user, collection=course, is_active=True)


def _make_quiz_form(*, submit_on_exit=False):
    """Create a minimal quiz form with one page and two questions."""
    form = FormFactory(
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
        submit_on_exit=submit_on_exit,
    )
    page = FormPageFactory(form=form, order=0)
    q1 = FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    QuestionOptionFactory(question=q1, correct=True)
    QuestionOptionFactory(question=q1, correct=False)
    q2 = FormQuestionFactory(form_page=page, type="multiple_choice", order=1)
    QuestionOptionFactory(question=q2, correct=True)
    QuestionOptionFactory(question=q2, correct=False)
    return form


def _make_two_page_form(*, submit_on_exit=False):
    """Create a form with two pages, one question each."""
    form = FormFactory(
        strategy=FormStrategy.CATEGORY_VALUE_SUM, submit_on_exit=submit_on_exit
    )
    page1 = FormPageFactory(form=form, order=0)
    q1 = FormQuestionFactory(form_page=page1, type="multiple_choice", order=0)
    QuestionOptionFactory(question=q1, correct=True)

    page2 = FormPageFactory(form=form, order=1)
    q2 = FormQuestionFactory(form_page=page2, type="multiple_choice", order=0)
    QuestionOptionFactory(question=q2, correct=True)
    return form, [page1, page2], [q1, q2]


# ---------------------------------------------------------------------------
# §4d — form_submit_and_exit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_submit_and_exit_post_completes_attempt_and_redirects(
    mock_site_context, client
):
    """POST to form_submit_and_exit completes an incomplete attempt and redirects to results."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    course = _make_course_with_form(form)
    _register(user, course)
    incomplete = FormProgressFactory(user=user, form=form)
    assert incomplete.completed_time is None

    client.force_login(user)
    url = reverse(
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)

    incomplete.refresh_from_db()
    assert incomplete.completed_time is not None

    assert response.status_code == 302
    expected_redirect = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_submit_and_exit_get_returns_405(mock_site_context, client):
    """GET to form_submit_and_exit is rejected with 405."""
    user = UserFactory()
    form = FormFactory()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    url = reverse(
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_form_submit_and_exit_with_no_incomplete_attempt_still_redirects(
    mock_site_context, client
):
    """POST to form_submit_and_exit when there is no incomplete attempt still redirects to results."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    course = _make_course_with_form(form)
    _register(user, course)
    # No incomplete attempt

    client.force_login(user)
    url = reverse(
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_submit_and_exit_requires_login(mock_site_context, client):
    """Unauthenticated POST to form_submit_and_exit redirects to login."""
    form = FormFactory()
    course = _make_course_with_form(form)

    url = reverse(
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


# ---------------------------------------------------------------------------
# §4c — answered_count reflects only persisted answers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_answered_count_reflects_only_persisted_answers_after_page_advance(
    mock_site_context, client
):
    """
    After answering page 1 and advancing (saving), answered_count on page 2 reflects
    those persisted answers from page 1. Answers typed on page 2 (not yet saved) are
    not counted.
    """
    user = UserFactory()
    form, _pages, questions = _make_two_page_form()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)

    # Start the form — creates a FormProgress
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # Get the form_progress that was created
    form_progress = FormProgress.get_latest_incomplete(user=user, form=form)
    assert form_progress is not None

    # POST page 1 to save the answer (this persists q1's answer)
    correct_option = questions[0].options.filter(correct=True).first()
    page1_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    client.post(page1_url, {f"question_{questions[0].id}": str(correct_option.id)})

    # Now on page 2, GET the runner page
    page2_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 2},
    )
    response = client.get(page2_url)

    assert response.status_code == 200
    # answered_count should be 1 (only persisted from page 1)
    assert response.context["answered_count"] == 1


@pytest.mark.django_db
def test_answered_count_does_not_include_unsaved_page_edits(mock_site_context, client):
    """
    answered_count reflects only persisted answers. A fresh GET to page 2
    with no answers submitted yet shows answered_count == 0.
    """
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)

    # Start form
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # GET page 1 without submitting any answers
    page1_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(page1_url)

    assert response.status_code == 200
    # No answers persisted yet
    assert response.context["answered_count"] == 0


# ---------------------------------------------------------------------------
# §4a — stale-attempt safety net: returning to submit-on-exit form finalises stale attempt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_form_finalises_stale_incomplete_for_submit_on_exit(
    mock_site_context, client
):
    """
    Visiting the start screen (view_form) for a submit-on-exit form when an
    incomplete attempt exists finalises it: the start screen no longer offers 'Continue'.
    """
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    course = _make_course_with_form(form)
    _register(user, course)

    # Create a stale incomplete attempt
    incomplete = FormProgressFactory(user=user, form=form)
    assert incomplete.completed_time is None

    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200

    # The stale attempt must be finalised
    incomplete.refresh_from_db()
    assert incomplete.completed_time is not None

    # The buttons must not offer "Continue" (no incomplete attempt remains)
    buttons = response.context["buttons"]
    button_actions = [b["action"] for b in buttons]
    assert "continue" not in button_actions


@pytest.mark.django_db
def test_form_start_finalises_stale_incomplete_for_submit_on_exit(
    mock_site_context, client
):
    """
    form_start for a submit-on-exit form when an incomplete attempt exists
    finalises the stale attempt and creates a fresh one.
    """
    user = UserFactory()
    form = FormFactory(submit_on_exit=True, strategy=FormStrategy.CATEGORY_VALUE_SUM)
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page, type="multiple_choice", order=0)
    course = _make_course_with_form(form)
    _register(user, course)

    # Create a stale incomplete attempt
    stale = FormProgressFactory(user=user, form=form)
    assert stale.completed_time is None

    client.force_login(user)
    url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    client.get(url)

    # Stale attempt is finalised
    stale.refresh_from_db()
    assert stale.completed_time is not None

    # A fresh attempt was created
    all_incomplete = FormProgress.objects.filter(
        user=user, form=form, completed_time__isnull=True
    )
    assert all_incomplete.count() == 1
    assert all_incomplete.first().pk != stale.pk


@pytest.mark.django_db
def test_view_form_save_on_exit_does_not_finalise_incomplete(mock_site_context, client):
    """
    For a save-on-exit form (default), visiting the start screen leaves
    the incomplete attempt intact and still offers 'Continue'.
    """
    user = UserFactory()
    form = FormFactory(submit_on_exit=False)
    course = _make_course_with_form(form)
    _register(user, course)

    incomplete = FormProgressFactory(user=user, form=form)

    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200

    incomplete.refresh_from_db()
    assert incomplete.completed_time is None

    buttons = response.context["buttons"]
    button_actions = [b["action"] for b in buttons]
    assert "continue" in button_actions


# ---------------------------------------------------------------------------
# §4b — view_form context (start screen)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_form_context_includes_question_count_and_page_count(
    mock_site_context, client
):
    """view_form provides question_count and page_count in context."""
    user = UserFactory()
    form = FormFactory()
    page1 = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page1, order=0)
    FormQuestionFactory(form_page=page1, order=1)
    page2 = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=page2, order=0)
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["question_count"] == 3
    assert response.context["page_count"] == 2


# ---------------------------------------------------------------------------
# §4c — runner context: no-store header, total_question_count, submit_and_exit_url
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_fill_page_sets_cache_control_no_store(mock_site_context, client):
    """GET to form_fill_page includes Cache-Control: no-store header."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    # Start the form first so a FormProgress exists
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.get("Cache-Control") == "no-store"


@pytest.mark.django_db
def test_form_fill_page_context_includes_total_question_count(
    mock_site_context, client
):
    """form_fill_page context includes total_question_count."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["total_question_count"] == 2  # 1 question per page, 2 pages


@pytest.mark.django_db
def test_form_fill_page_context_includes_submit_and_exit_url(mock_site_context, client):
    """form_fill_page context includes submit_and_exit_url."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    expected_exit_url = reverse(
        "student_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response.context["submit_and_exit_url"] == expected_exit_url


@pytest.mark.django_db
def test_form_fill_page_context_includes_submit_on_exit(mock_site_context, client):
    """form_fill_page context includes form.submit_on_exit."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form(submit_on_exit=True)
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["form"].submit_on_exit is True


# ---------------------------------------------------------------------------
# §4e — course_form_complete context: percentage for QUIZ
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_form_complete_includes_percentage_for_quiz(mock_site_context, client):
    """course_form_complete context includes percentage for QUIZ forms."""
    user = UserFactory()
    form = _make_quiz_form()
    course = _make_course_with_form(form)
    _register(user, course)

    # Create a completed form progress with a known score
    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 2, "max_score": 2},
    )

    client.force_login(user)
    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["percentage"] == 100


@pytest.mark.django_db
def test_course_form_complete_percentage_reflects_partial_score(
    mock_site_context, client
):
    """course_form_complete percentage is proportional to the score."""
    user = UserFactory()
    form = _make_quiz_form()
    course = _make_course_with_form(form)
    _register(user, course)

    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )

    client.force_login(user)
    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["percentage"] == 50


@pytest.mark.django_db
def test_course_form_complete_no_percentage_for_non_quiz(mock_site_context, client):
    """course_form_complete does not include percentage for non-QUIZ forms."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    course = _make_course_with_form(form)
    _register(user, course)

    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"Uncategorized": {"score": 1, "max_score": 1, "sub_categories": {}}},
    )

    client.force_login(user)
    url = reverse(
        "student_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "percentage" not in response.context


# ---------------------------------------------------------------------------
# count_form_questions helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_count_form_questions_returns_total_across_all_pages(mock_site_context):
    """count_form_questions returns the total question count across all pages."""
    from freedom_ls.student_interface.utils import count_form_questions

    form = FormFactory()
    page1 = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page1, order=0)
    FormQuestionFactory(form_page=page1, order=1)
    page2 = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=page2, order=0)

    assert count_form_questions(form) == 3


@pytest.mark.django_db
def test_count_form_questions_returns_zero_for_form_with_no_questions(
    mock_site_context,
):
    """count_form_questions returns 0 for a form with no questions."""
    from freedom_ls.student_interface.utils import count_form_questions

    form = FormFactory()
    assert count_form_questions(form) == 0
