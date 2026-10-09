from __future__ import annotations

import html
import re

import pytest

from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.models import Course
from freedom_ls.content_engine.tests.helpers import collection_item_for
from freedom_ls.form_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormProgressFactory,
    FormQuestionFactory,
    QuestionAnswerFactory,
    QuestionOptionFactory,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.form_engine.queries import count_form_questions
from freedom_ls.learner_interface.tests.helpers import course_with_form, form_attempt
from freedom_ls.learner_interface.utils import form_start_page_buttons, get_course_index
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.tests.helpers import register_user_for_course
from freedom_ls.learner_progress.attempts import (
    get_latest_incomplete,
    get_or_create_incomplete,
)
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.tests.helpers import course_progress_record

# Form-runner view tests: stale-attempt safety net, runner context, form_submit_and_exit.


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _exit_url(course: Course) -> str:
    return reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )


# ---------------------------------------------------------------------------
# form_submit_and_exit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_submit_and_exit_post_completes_attempt_and_redirects(
    mock_site_context, client
):
    """POST to form_submit_and_exit completes an incomplete attempt and redirects to results."""
    user = UserFactory()
    form = FormFactory(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    incomplete = form_attempt(course, user, form)
    assert incomplete.completed_time is None

    client.force_login(user)
    url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)

    incomplete.refresh_from_db()
    assert incomplete.completed_time is not None

    assert response.status_code == 302
    expected_redirect = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_submit_and_exit_get_returns_405(mock_site_context, client):
    """GET to form_submit_and_exit is rejected with 405."""
    user = UserFactory()
    form = FormFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:form_submit_and_exit",
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
    course = course_with_form(form)
    register_user_for_course(course, user)
    # No incomplete attempt

    client.force_login(user)
    url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_submit_and_exit_does_not_finalise_save_on_exit_form(
    mock_site_context, client
):
    """A direct POST must not force-complete a save-on-exit form's attempt.

    The exit dialog only renders this POST for submit-on-exit forms, but the
    endpoint is reachable directly. Save-on-exit forms promise the attempt is
    saved (resumable), not scored, so the attempt stays incomplete and the
    learner is sent back to the form start screen.
    """
    user = UserFactory()
    form = FormFactory(submit_on_exit=False)
    course = course_with_form(form)
    register_user_for_course(course, user)
    incomplete = form_attempt(course, user, form)
    assert incomplete.completed_time is None

    client.force_login(user)
    url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)

    incomplete.refresh_from_db()
    assert incomplete.completed_time is None

    assert response.status_code == 302
    expected_redirect = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_submit_and_exit_requires_login(mock_site_context, client):
    """Unauthenticated POST to form_submit_and_exit redirects to login."""
    form = FormFactory()
    course = course_with_form(form)

    url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.post(url)
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


# ---------------------------------------------------------------------------
# answered_count reflects only persisted answers
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)

    # Start the form — creates a FormProgress
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # Get the form_progress that was created
    form_progress = get_latest_incomplete(
        course_progress_record(course, user), collection_item_for(course, form)
    )
    assert form_progress is not None

    # POST page 1 to save the answer (this persists q1's answer)
    correct_option = questions[0].options.filter(correct=True).first()
    page1_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    client.post(page1_url, {f"question_{questions[0].id}": str(correct_option.id)})

    # Now on page 2, GET the runner page
    page2_url = reverse(
        "learner_interface:form_fill_page",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)

    # Start form
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # GET page 1 without submitting any answers
    page1_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(page1_url)

    assert response.status_code == 200
    # No answers persisted yet
    assert response.context["answered_count"] == 0


@pytest.mark.django_db
def test_answered_other_pages_excludes_current_page_questions(
    mock_site_context, client
):
    """
    answered_other_pages is the base for the live client-side count: it counts
    persisted answers for questions NOT on the current page, so the current
    page's own answers are not double-counted by the live in-browser tally.

    After saving page 1, the final page (page 2) sees that one persisted answer
    as a base of 1; revisiting page 1 sees a base of 0 (its own answer is on the
    current page).
    """
    user = UserFactory()
    form, _pages, questions = _make_two_page_form()
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # Persist page 1's answer.
    correct_option = questions[0].options.filter(correct=True).first()
    page1_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    client.post(page1_url, {f"question_{questions[0].id}": str(correct_option.id)})

    # On the final page, page 1's persisted answer is "another page" → base 1.
    page2_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 2},
    )
    assert client.get(page2_url).context["answered_other_pages"] == 1

    # Back on page 1, its own persisted answer is on the current page → base 0.
    assert client.get(page1_url).context["answered_other_pages"] == 0


# ---------------------------------------------------------------------------
# stale-attempt safety net: returning to submit-on-exit form finalises stale attempt
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    # Create a stale incomplete attempt
    incomplete = form_attempt(course, user, form)
    assert incomplete.completed_time is None

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    # Create a stale incomplete attempt
    stale = form_attempt(course, user, form)
    assert stale.completed_time is None

    client.force_login(user)
    url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    client.get(url)

    # Stale attempt is finalised
    stale.refresh_from_db()
    assert stale.completed_time is not None

    # A fresh attempt was created
    all_incomplete = CourseFormAttempt.objects.filter(
        course_progress=course_progress_record(course, user),
        collection_item=collection_item_for(course, form),
        form_progress__completed_time__isnull=True,
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    incomplete = form_attempt(course, user, form)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
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
# view_form context (start screen)
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["question_count"] == 3
    assert response.context["page_count"] == 2


@pytest.mark.django_db
def test_form_start_page_shows_question_and_page_counts(mock_site_context, client):
    """The rendered start screen names the question and page counts."""
    user = UserFactory()
    form = FormFactory()
    page1 = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page1, order=0)
    FormQuestionFactory(form_page=page1, order=1)
    page2 = FormPageFactory(form=form, order=1)
    FormQuestionFactory(form_page=page2, order=0)
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    content = response.content.decode()

    assert "3 questions" in content
    assert "2 pages" in content


@pytest.mark.django_db
def test_form_start_page_counts_are_singular_for_one(mock_site_context, client):
    """A one-question, one-page form is described in the singular."""
    user = UserFactory()
    form = FormFactory()
    page = FormPageFactory(form=form, order=0)
    FormQuestionFactory(form_page=page, order=0)
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    content = response.content.decode()

    assert re.search(r"1 question(?!s)", content)
    assert re.search(r"1 page(?!s)", content)


@pytest.mark.django_db
def test_form_subtitle_renders_as_eyebrow(mock_site_context, client):
    """A form with a subtitle renders that text inside a <p> above its title."""
    user = UserFactory()
    form = FormFactory(subtitle="Section One")
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    content = response.content.decode()

    pattern = (
        rf"<p[^>]*>\s*{re.escape(form.subtitle)}\s*</p>\s*"
        rf"<h1[^>]*>\s*{re.escape(str(form.title))}"
    )
    assert re.search(pattern, content, re.DOTALL)


@pytest.mark.django_db
def test_form_without_subtitle_renders_no_eyebrow(mock_site_context, client):
    """A form with a blank subtitle renders no empty eyebrow element."""
    user = UserFactory()
    form = FormFactory(subtitle="")
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    content = response.content.decode()

    h1_match = re.search(rf"<h1[^>]*>\s*{re.escape(str(form.title))}", content)
    assert h1_match is not None
    preceding = content[: h1_match.start()].rstrip()
    assert not preceding.endswith("</p>")


@pytest.mark.django_db
def test_view_form_start_screen_title_in_tab_but_not_duplicated(
    mock_site_context, client
):
    """The form start screen names the form in the browser <title> only once.

    The start screen renders its own in-content title (eyebrow + <h1>), so the
    shared header `page_title` block is intentionally omitted to avoid a
    duplicate visible heading. The `item_head_title` block must remain, however,
    so the browser tab still names the form rather than starting with " — ".
    """
    user = UserFactory()
    form = FormFactory(title="Distinctive Form Title")
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Browser tab title names the form (item_head_title block).
    head_title = content.split("<title>")[1].split("</title>")[0]
    assert "Distinctive Form Title" in head_title
    assert not head_title.lstrip().startswith("—")

    # The shared header title wrapper is present but does not duplicate the
    # in-content heading.
    page_title_wrapper = content.split('id="page-title"')[1].split("</hgroup>")[0]
    assert "Distinctive Form Title" not in page_title_wrapper


# ---------------------------------------------------------------------------
# runner context: no-store header, total_question_count, submit_and_exit_url
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_fill_page_sets_cache_control_no_store(mock_site_context, client):
    """GET to form_fill_page includes Cache-Control: no-store header."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    # Start the form first so a FormProgress exists
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "learner_interface:form_fill_page",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "learner_interface:form_fill_page",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    expected_exit_url = reverse(
        "learner_interface:form_submit_and_exit",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response.context["submit_and_exit_url"] == expected_exit_url


@pytest.mark.django_db
def test_save_on_exit_dialog_renders_real_view_course_item_url(
    mock_site_context, client
):
    """The save-on-exit exit dialog renders a real view_course_item URL.

    Regression: the "Leave and save" link used a `{% url %}` tag in a c-button
    href on a continuation line, which django-cotton passed through literally,
    producing a 404 redirect to the unrendered template tag.
    """
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form(submit_on_exit=False)
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    expected_url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    # The "Leave and save" link must point at the real save-and-exit URL.
    assert f'href="{expected_url}"' in content
    # The unrendered template tag must not leak into the HTML (cotton would
    # otherwise pass the literal `{% url ... %}` through, HTML-escaped).
    assert "{% url" not in content


@pytest.mark.django_db
def test_form_fill_page_context_includes_submit_on_exit(mock_site_context, client):
    """form_fill_page context includes form.submit_on_exit."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["form"].submit_on_exit is True


# ---------------------------------------------------------------------------
# course_form_complete context: percentage for QUIZ
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_course_form_complete_includes_percentage_for_quiz(mock_site_context, client):
    """course_form_complete context includes percentage for QUIZ forms."""
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)

    # Create a completed form progress with a known score
    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 2, "max_score": 2},
    )

    client.force_login(user)
    url = reverse(
        "learner_interface:course_form_complete",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )

    client.force_login(user)
    url = reverse(
        "learner_interface:course_form_complete",
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
    course = course_with_form(form)
    register_user_for_course(course, user)

    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"Uncategorized": {"score": 1, "max_score": 1, "sub_categories": {}}},
    )

    client.force_login(user)
    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    # The quiz score ring (which surfaces a percentage) is only rendered for
    # QUIZ forms. The surrounding course chrome exposes its own course-progress
    # `percentage`, so assert on the rendered quiz element rather than the
    # aggregated template context.
    assert b'data-testid="quiz-percentage"' not in response.content


@pytest.mark.django_db
def test_course_form_complete_renders_incorrect_checkbox_answer_with_every_selection(
    mock_site_context, client
):
    """Regression test for the exact-match scoring fix: a learner who ticks every option on
    a checkbox question is now correctly marked wrong, and the incorrect-answers block
    renders every option the learner selected, not just the one that used to short-circuit
    the old any-correct-option rule."""
    user = UserFactory()
    form = FormFactory(
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=70,
        quiz_show_incorrect=True,
    )
    course = course_with_form(form)
    register_user_for_course(course, user)

    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(
        form_page=page, type="checkboxes", order=0, question="Pick the primes"
    )
    correct_1 = QuestionOptionFactory(
        question=question, text="2", correct=True, order=0
    )
    correct_2 = QuestionOptionFactory(
        question=question, text="3", correct=True, order=1
    )
    wrong_1 = QuestionOptionFactory(question=question, text="4", correct=False, order=2)

    form_progress: FormProgress = form_attempt(course, user, form)
    answer = QuestionAnswerFactory(form_progress=form_progress, question=question)
    answer.selected_options.add(correct_1, correct_2, wrong_1)
    form_progress.complete()

    client.force_login(user)
    url = reverse(
        "learner_interface:course_form_complete",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["quiz_verdict"] == "failed"
    incorrect_answers = response.context["incorrect_answers"]
    assert [item["question"] for item in incorrect_answers] == [question]
    assert set(incorrect_answers[0]["learner_selected"]) == {
        correct_1,
        correct_2,
        wrong_1,
    }
    assert b'data-testid="incorrect-answers-section"' in response.content


def _completed_quiz_results_page(client, *, score, max_score):
    """Complete a quiz that HAS a pass mark of 70% and return the results page."""
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": score, "max_score": max_score},
    )
    client.force_login(user)
    return client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )


@pytest.mark.django_db
def test_results_page_with_pass_mark_shows_passed_banner(mock_site_context, client):
    response = _completed_quiz_results_page(client, score=2, max_score=2)

    assert response.context["quiz_verdict"] == "passed"
    assert "Quiz passed!" in response.content.decode()


@pytest.mark.django_db
def test_results_page_with_pass_mark_shows_not_passed_banner(mock_site_context, client):
    response = _completed_quiz_results_page(client, score=1, max_score=2)

    assert response.context["quiz_verdict"] == "failed"
    assert "Quiz not passed" in response.content.decode()


@pytest.mark.django_db
def test_results_page_with_failed_verdict_offers_a_retry(mock_site_context, client):
    response = _completed_quiz_results_page(client, score=1, max_score=2)

    assert "Retry quiz" in response.content.decode()


# ---------------------------------------------------------------------------
# count_form_questions helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_count_form_questions_returns_total_across_all_pages(mock_site_context):
    """count_form_questions returns the total question count across all pages."""
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
    form = FormFactory()
    assert count_form_questions(form) == 0


# ---------------------------------------------------------------------------
# Runner page rendering (QA report bug fixes)
# ---------------------------------------------------------------------------


def _start_runner(client, user, form):
    """Register the user, force-login, and GET the runner fill page (following
    the form_start redirect). Returns the rendered fill-page response."""
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    start_url = reverse(
        "learner_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    return client.get(start_url, follow=True)


@pytest.mark.django_db
def test_runner_page_loads_content_engine_alpine_components(mock_site_context, client):
    """The runner must load content_engine's Alpine components.

    Regression (QA report bug 1): the runner base only loaded
    learner_interface's Alpine components, so contentLightbox/onEscape were
    undefined — a markdown image in a question logged console errors and its
    lightbox covered the runner, blocking submission. The runner must include
    content_engine/js/alpine-components.js (like the normal course pages do).
    """
    user = UserFactory()
    form = _make_quiz_form()

    response = _start_runner(client, user, form)

    assert response.status_code == 200
    content = response.content.decode()
    assert "content_engine/js/alpine-components.js" in content


@pytest.mark.django_db
def test_runner_sr_only_heading_labels_pages_not_questions(mock_site_context, client):
    """The sr-only runner heading announces the page, not "Question".

    Regression (QA report bug 3): the heading rendered "<title> — Question
    {page} of {total}", mislabelling pages as questions. The numbers are page
    numbers, so the literal word must be "Page".
    """
    user = UserFactory()
    form = _make_quiz_form()

    response = _start_runner(client, user, form)

    assert response.status_code == 200
    content = response.content.decode()
    assert "— Page 1 of" in content
    assert "— Question 1 of" not in content


@pytest.mark.django_db
def test_final_page_submit_button_is_a_real_form_submit(mock_site_context, client):
    """No-JS fallback: the final-page primary button must be a real submit
    targeting the page form, so the attempt can be submitted (and server-side
    completed/scored) without JavaScript. With JS, x-on:click.prevent opens the
    review dialog instead, but the markup must degrade gracefully.
    """
    user = UserFactory()
    form = _make_quiz_form()  # single page → the runner GET lands on the final page

    response = _start_runner(client, user, form)

    assert response.status_code == 200
    content = response.content.decode()
    assert re.search(r'type="submit"\s+form="runner-page-form"', content)


@pytest.mark.django_db
def test_the_submit_dialog_is_drawn_only_on_the_final_page(mock_site_context, client):
    """The review dialog belongs to the end of the form. A page with more to
    come offers Next instead, and must not carry a second dialog that the exit
    focus trap could reach."""
    user = UserFactory()
    form, _pages, _questions = _make_two_page_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    first = client.get(_fill_page_url(course, 1)).content.decode()
    last = client.get(_fill_page_url(course, 2)).content.decode()

    assert 'aria-labelledby="submit-dialog-title"' not in first
    assert 'aria-labelledby="submit-dialog-title"' in last


# ---------------------------------------------------------------------------
# form_fill_page POST with no incomplete attempt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_fill_page_post_with_no_incomplete_attempt_redirects(
    mock_site_context, client
):
    """POST to form_fill_page with no incomplete attempt redirects, not 500.

    get_latest_incomplete() returns None when there is no incomplete attempt
    (e.g. a submit-on-exit attempt was finalised by the stale-attempt safety
    net, or the page was reached without starting). The POST branch must not
    dereference None — it sends the learner back to the form start screen.
    """
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    # No FormProgress created — POST straight to the fill page.
    page_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.post(page_url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


@pytest.mark.django_db
def test_form_fill_page_get_with_no_incomplete_attempt_redirects(
    mock_site_context, client
):
    """GET to form_fill_page with no incomplete attempt redirects, not 500.

    get_latest_incomplete() returns None when there is no incomplete attempt
    (e.g. the form is already completed). The GET branch must guard this case
    exactly as the POST branch does, rather than dereferencing None and raising
    AttributeError ('NoneType' object has no attribute 'existing_answers_dict').
    """
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    # A completed attempt exists, so there is no incomplete attempt to resume.
    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 2, "max_score": 2},
    )

    page_url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(page_url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


# ---------------------------------------------------------------------------
# previous-attempts summary shows up to the 5 latest attempts, newest first
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_form_previous_attempts_shows_multiple_newest_first(
    mock_site_context, client
):
    """The start-screen previous-attempts summary shows every completed attempt
    (more than one), ordered newest-first, when there are 5 or fewer."""
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    now = timezone.now()
    older = form_attempt(
        course,
        user,
        form,
        completed_time=now - timezone.timedelta(hours=2),
        scores={"score": 0, "max_score": 2},
    )
    middle = form_attempt(
        course,
        user,
        form,
        completed_time=now - timezone.timedelta(hours=1),
        scores={"score": 1, "max_score": 2},
    )
    most_recent = form_attempt(
        course,
        user,
        form,
        completed_time=now,
        scores={"score": 2, "max_score": 2},
    )

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    completed = list(response.context["completed_form_progress"])
    assert completed == [most_recent, middle, older]


@pytest.mark.django_db
def test_view_form_previous_attempts_capped_at_five(mock_site_context, client):
    """When more than 5 attempts exist, only the 5 latest are shown."""
    user = UserFactory()
    form = _make_quiz_form()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)

    now = timezone.now()
    attempts = [
        form_attempt(
            course,
            user,
            form,
            completed_time=now - timezone.timedelta(hours=offset),
            scores={"score": 1, "max_score": 2},
        )
        for offset in range(7)
    ]
    # attempts[0] is newest (offset 0); attempts[6] is oldest.

    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    completed = list(response.context["completed_form_progress"])
    assert completed == attempts[:5]
    assert attempts[5] not in completed
    assert attempts[6] not in completed


# ---------------------------------------------------------------------------
# "Leave and submit" carries the current page's answers (QA report bug 2)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submit_and_exit_scores_the_answers_posted_with_it(mock_site_context, client):
    """Leaving a submit-on-exit form scores the answers on the page being left.

    Regression (QA report bug 2): the exit dialog posted its own empty form, so
    the current page's answers were never persisted and the attempt — which a
    submit-on-exit form will not let the learner re-sit — locked in 0%.
    """
    user = UserFactory()
    form = _make_quiz_form(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    page = form.pages.first()
    q1, q2 = list(page.questions.all())
    client.post(
        _exit_url(course),
        {
            "page_number": "1",
            f"question_{q1.id}": str(q1.options.get(correct=True).id),
            f"question_{q2.id}": str(q2.options.get(correct=False).id),
        },
    )

    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.completed_time is not None
    assert attempt.scores == {"score": 1, "max_score": 2}


@pytest.mark.django_db
def test_submit_and_exit_does_not_enforce_required_answers(mock_site_context, client):
    """Leaving scores the attempt as it stands — a blank required question is
    not a gate on the way out, unlike the Next/Submit path."""
    user = UserFactory()
    form = _make_quiz_form(submit_on_exit=True)
    page = form.pages.first()
    page.questions.update(required=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    q1, _q2 = list(page.questions.all())
    response = client.post(
        _exit_url(course),
        {"page_number": "1", f"question_{q1.id}": str(q1.options.get(correct=True).id)},
    )

    assert response.status_code == 302
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.scores == {"score": 1, "max_score": 2}


@pytest.mark.django_db
def test_submit_and_exit_leaves_other_pages_answers_alone(mock_site_context, client):
    """save_answers clears any question it is handed no answer for, so the exit
    endpoint must scope itself to the page that was actually posted."""
    user = UserFactory()
    form, _pages, questions = _make_two_page_form(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # Persist page 1's answer the normal way, then leave from page 2.
    client.post(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        ),
        {f"question_{questions[0].id}": str(questions[0].options.first().id)},
    )
    client.post(
        _exit_url(course),
        {
            "page_number": "2",
            f"question_{questions[1].id}": str(questions[1].options.first().id),
        },
    )

    attempt = FormProgress.objects.get(user=user, form=form)
    answered_question_ids = set(attempt.answers.values_list("question_id", flat=True))
    assert answered_question_ids == {questions[0].id, questions[1].id}


@pytest.mark.django_db
def test_submit_and_exit_without_a_page_number_still_completes(
    mock_site_context, client
):
    """A direct POST carrying no page context finalises what was already saved,
    exactly as it did before the exit dialog started posting answers."""
    user = UserFactory()
    form = _make_quiz_form(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    incomplete = get_or_create_incomplete(
        course_progress_record(course, user), collection_item_for(course, form)
    )

    client.force_login(user)
    response = client.post(_exit_url(course), {"page_number": "not a page"})

    incomplete.refresh_from_db()
    assert incomplete.completed_time is not None
    assert response.status_code == 302


@pytest.mark.django_db
def test_runner_page_form_carries_its_page_number(mock_site_context, client):
    """The runner page form names its page, so the exit endpoint — whose URL has
    no page in it — knows which questions the POST belongs to."""
    user = UserFactory()
    form = _make_quiz_form(submit_on_exit=True)

    response = _start_runner(client, user, form)

    assert response.status_code == 200
    assert re.search(
        r'<input[^>]*name="page_number"[^>]*value="1"', response.content.decode()
    )


@pytest.mark.django_db
def test_exit_dialog_leave_and_submit_targets_the_runner_page_form(
    mock_site_context, client
):
    """ "Leave and submit" must submit the runner page form, retargeted at the
    exit endpoint, rather than a second form that carries no answers."""
    user = UserFactory()
    form = _make_quiz_form(submit_on_exit=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    response = client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )

    assert response.status_code == 200
    content = response.content.decode()
    exit_url = _exit_url(course)

    # No second <form> posting to the exit endpoint with no fields in it.
    assert not re.search(rf'<form[^>]*\saction="{re.escape(exit_url)}"', content)

    button_match = re.search(
        r'<[^>]*data-testid="leave-and-submit-button"[^>]*>', content
    )
    assert button_match is not None
    button = button_match.group(0)
    assert 'form="runner-page-form"' in button
    assert f'formaction="{exit_url}"' in button
    # Leaving must not be blocked by the browser's required-field validation.
    assert "formnovalidate" in button


# ---------------------------------------------------------------------------
# Decorative badge icon must be hidden from assistive technology
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_form_start_badge_wrapper_is_hidden_from_assistive_technology(
    mock_site_context, client
):
    """The decorative badge icon next to the form title carries no
    information the title doesn't already convey, so its wrapper must be
    marked aria-hidden to keep it out of the accessibility tree."""
    user = UserFactory()
    form = FormFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)

    client.force_login(user)
    url = reverse(
        "learner_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)
    content = response.content.decode()

    badge_match = re.search(r"<div[^>]*\bbg-secondary\b[^>]*>", content)
    assert badge_match is not None
    assert 'aria-hidden="true"' in badge_match.group(0)


@pytest.mark.django_db
def test_form_start_resumes_past_a_skipped_optional_question(mock_site_context, client):
    """A skipped optional question leaves no answer row, so the first-outstanding
    page sits behind where the learner actually reached. Resuming there would
    drop them in front of pages they have already worked through.
    """
    form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    pages = [FormPageFactory(form=form, order=order) for order in range(4)]
    questions = [
        FormQuestionFactory(
            form_page=page, type="short_text", order=0, required=index != 1
        )
        for index, page in enumerate(pages)
    ]
    course = course_with_form(form)
    user = UserFactory()
    register_user_for_course(course, user)
    attempt = form_attempt(course, user, form)
    for index in (0, 2, 3):
        QuestionAnswerFactory(
            form_progress=attempt, question=questions[index], text_answer="done"
        )

    client.force_login(user)
    response = client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    assert response["Location"] == reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 4},
    )


# ---------------------------------------------------------------------------
# Rejected (invalid) typed answers
# ---------------------------------------------------------------------------


def _make_single_question_form(question_type: str, *, required: bool = False):
    """A one-page, one-question form, isolated from the multi-question forms
    above so a rejected answer's effect on paging and completion is
    unambiguous."""
    form = FormFactory(strategy=FormStrategy.UNSCORED)
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(
        form_page=page, type=question_type, order=0, required=required
    )
    return form, question


def _fill_page_url(course: Course, page_number: int = 1) -> str:
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )


@pytest.mark.django_db
def test_an_invalid_date_answer_returns_422_and_stores_nothing(
    mock_site_context, client
):
    user = UserFactory()
    form, question = _make_single_question_form("date")
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    response = client.post(
        _fill_page_url(course), {f"question_{question.id}": "banana"}
    )

    assert response.status_code == 422
    assert (
        response.context["rejected_answers_error"] == "Question 1 needs a valid answer."
    )
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.answers.filter(question=question).count() == 0


@pytest.mark.django_db
def test_a_rejected_email_comes_back_in_the_input_value(mock_site_context, client):
    user = UserFactory()
    form, question = _make_single_question_form("email")
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    body = client.post(
        _fill_page_url(course), {f"question_{question.id}": "not-an-email"}
    ).content.decode()

    assert 'value="not-an-email"' in body


@pytest.mark.django_db
def test_a_corrected_resubmission_advances_and_stores(mock_site_context, client):
    user = UserFactory()
    form, question = _make_single_question_form("email")
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    client.post(_fill_page_url(course), {f"question_{question.id}": "not-an-email"})

    response = client.post(
        _fill_page_url(course), {f"question_{question.id}": "ada@example.com"}
    )

    assert response.status_code == 302
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.answers.get(question=question).text_answer == "ada@example.com"


@pytest.mark.django_db
def test_a_rejected_required_answer_does_not_complete_the_attempt(
    mock_site_context, client
):
    """The rejected date stores no row, so the single-page final submission
    does not satisfy the required check and does not complete the attempt."""
    user = UserFactory()
    form, question = _make_single_question_form("date", required=True)
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    response = client.post(
        _fill_page_url(course), {f"question_{question.id}": "banana"}
    )

    assert response.status_code == 422
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.completed_time is None


# ---------------------------------------------------------------------------
# "Leave and submit" meets a rejected answer
# ---------------------------------------------------------------------------


def _start_submit_on_exit_attempt(client, question_type: str, *, required=False):
    """A started attempt on a one-question submit-on-exit form."""
    user = UserFactory()
    form, question = _make_single_question_form(question_type, required=required)
    form.submit_on_exit = True
    form.save()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    return user, form, question, course


@pytest.mark.django_db
def test_leave_and_submit_with_an_invalid_answer_does_not_complete_the_attempt(
    mock_site_context, client
):
    """The exit button is `formnovalidate`, so an invalid value reaches the
    server unchecked. Finalising on it would freeze the attempt without the
    answer and leave no chance to fix it."""
    user, form, question, course = _start_submit_on_exit_attempt(client, "date")

    response = client.post(
        _exit_url(course),
        {"page_number": "1", f"question_{question.id}": "banana"},
    )

    assert response.status_code == 422
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.completed_time is None
    assert attempt.answers.filter(question=question).count() == 0


@pytest.mark.django_db
def test_leave_and_submit_with_an_invalid_answer_still_records_the_page_reached(
    mock_site_context, client
):
    """Being sent back to the page is still having been shown it. The resume
    point is recorded where the page is rendered, so both ways of arriving --
    paging into it, and being returned to it by a refused exit -- move it."""
    user, form, question, course = _start_submit_on_exit_attempt(client, "date")

    client.post(
        _exit_url(course),
        {"page_number": "1", f"question_{question.id}": "banana"},
    )

    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.furthest_page_reached == 1


@pytest.mark.django_db
def test_leave_and_submit_with_an_invalid_answer_names_the_question(
    mock_site_context, client
):
    _user, _form, question, course = _start_submit_on_exit_attempt(client, "date")

    response = client.post(
        _exit_url(course),
        {"page_number": "1", f"question_{question.id}": "banana"},
    )

    assert (
        response.context["rejected_answers_error"] == "Question 1 needs a valid answer."
    )


@pytest.mark.django_db
def test_leave_and_submit_still_completes_when_a_required_answer_is_blank(
    mock_site_context, client
):
    """Leaving scores the attempt as it stands. A blank required question must
    not trap the learner in the exit dialog -- only an invalid one does."""
    user, form, _question, course = _start_submit_on_exit_attempt(
        client, "date", required=True
    )

    response = client.post(_exit_url(course), {"page_number": "1"})

    assert response.status_code == 302
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.completed_time is not None


@pytest.mark.django_db
def test_leave_and_submit_completes_once_the_answer_is_corrected(
    mock_site_context, client
):
    user, form, question, course = _start_submit_on_exit_attempt(client, "date")
    client.post(
        _exit_url(course), {"page_number": "1", f"question_{question.id}": "banana"}
    )

    response = client.post(
        _exit_url(course),
        {"page_number": "1", f"question_{question.id}": "2025-06-15"},
    )

    assert response.status_code == 302
    attempt = FormProgress.objects.get(user=user, form=form)
    assert attempt.completed_time is not None
    assert attempt.answers.get(question=question).text_answer == "2025-06-15"


@pytest.mark.django_db
def test_a_rejected_number_is_recited_in_its_error_message(mock_site_context, client):
    """The page sends the value back, but a browser blanks whatever it cannot
    parse out of a `number` input — the same value-sanitisation rule `date` and
    `time` inputs follow, so the field renders empty whatever we put in it.
    Reciting the value in the error message is what keeps the person's own
    words on the page for those three types."""
    user = UserFactory()
    form, question = _make_single_question_form("number")
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    body = client.post(
        _fill_page_url(course), {f"question_{question.id}": "banana"}
    ).content.decode()

    assert 'You entered "banana". Enter a whole number.' in html.unescape(body)


# Page-jump navigation on the form runner: which page dots a learner can click.


def _survey_with_an_optional_first_question(*, page_count: int) -> Form:
    """A multi-page survey whose first page holds a question a learner may skip."""
    form: Form = FormFactory(strategy=FormStrategy.CATEGORY_VALUE_SUM)
    optional_page = FormPageFactory(form=form, order=0, title="Page 1")
    optional_question = FormQuestionFactory(
        form_page=optional_page,
        type="multiple_choice",
        question="How are you finding this so far?",
        required=False,
        order=0,
    )
    QuestionOptionFactory(question=optional_question, text="Fine", order=0)

    for order in range(1, page_count):
        page = FormPageFactory(form=form, order=order, title=f"Page {order + 1}")
        question = FormQuestionFactory(
            form_page=page, type="multiple_choice", question="Pick one", order=0
        )
        QuestionOptionFactory(question=question, text="Alpha", order=0)
    return form


def _accessibility_of_each_page(client, course, page_number: int) -> list[bool]:
    url = reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )
    response = client.get(url)
    return [link["is_accessible"] for link in response.context["page_links"]]


@pytest.mark.django_db
def test_skipping_an_optional_question_keeps_the_reached_pages_clickable(
    mock_site_context, client
):
    """A skipped question stores no answer row, which must not lock the learner out."""
    form = _survey_with_an_optional_first_question(page_count=3)
    course = course_with_form(form)
    user = register_user_for_course(course)
    form_attempt(course, user, form)
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=3)

    assert accessibility == [True, True, True]


@pytest.mark.django_db
def test_pages_beyond_the_one_being_viewed_stay_locked(mock_site_context, client):
    form = _survey_with_an_optional_first_question(page_count=4)
    course = course_with_form(form)
    user = register_user_for_course(course)
    form_attempt(course, user, form)
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=2)

    assert accessibility == [True, True, False, False]


@pytest.mark.django_db
def test_an_answered_later_page_stays_clickable_from_the_first_page(
    mock_site_context, client
):
    """Progress already recorded still opens up the pages it reached."""
    form = _survey_with_an_optional_first_question(page_count=3)
    course = course_with_form(form)
    user = register_user_for_course(course)
    progress = form_attempt(course, user, form)
    third_page_question = form.pages.get(order=2).questions.get(order=0)
    QuestionAnswerFactory(
        form_progress=progress, question=third_page_question
    ).selected_options.add(third_page_question.options.get(order=0))
    client.force_login(user)

    accessibility = _accessibility_of_each_page(client, course, page_number=1)

    assert accessibility == [True, True, True]


@pytest.mark.django_db
def test_stepping_back_keeps_the_reached_page_clickable(mock_site_context, client):
    """Going back to page 1 after reaching page 2 must not re-lock page 2."""
    form = _survey_with_an_optional_first_question(page_count=3)
    course = course_with_form(form)
    user = register_user_for_course(course)
    form_attempt(course, user, form)
    client.force_login(user)
    _accessibility_of_each_page(client, course, page_number=2)

    accessibility = _accessibility_of_each_page(client, course, page_number=1)

    assert accessibility == [True, True, False]


# What the results page tells a learner about the answers it marked wrong.


def _checkbox_quiz(**form_kwargs):
    """A one-question checkbox quiz with two correct options and one incorrect."""
    form = FormFactory(
        title="Multi-Select Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=80,
        quiz_show_incorrect=True,
        **form_kwargs,
    )
    page = FormPageFactory(form=form, title="Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page,
        question="Which of these are mammals?",
        type="checkboxes",
        order=0,
    )
    dolphin = QuestionOptionFactory(
        question=question, text="Dolphin", value="dolphin", order=0, correct=True
    )
    bat = QuestionOptionFactory(
        question=question, text="Bat", value="bat", order=1, correct=True
    )
    crocodile = QuestionOptionFactory(
        question=question, text="Crocodile", value="crocodile", order=2, correct=False
    )
    return form, question, dolphin, bat, crocodile


def _registered_learner(course):
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    return user


def _results(client_factory, user, course):
    client = client_factory(user)
    return client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )


@pytest.mark.django_db
def test_a_question_left_blank_is_named_in_the_review_section(
    mock_site_context, logged_in_client
):
    """Failing a learner over a blank question and then not naming it tells them nothing."""
    form, _question, _dolphin, _bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Blank Course", slug="blank-course")
    user = _registered_learner(course)
    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )

    content = _results(logged_in_client, user, course).content.decode()

    assert 'data-testid="incorrect-answers-section"' in content
    assert "Which of these are mammals?" in content
    assert "did not answer" in content


@pytest.mark.django_db
def test_a_correctly_ticked_option_is_not_marked_as_an_error(
    mock_site_context, logged_in_client
):
    """The answer as a whole is wrong, but the ticks that were right must not read as wrong."""
    form, question, dolphin, bat, crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Glyph Course", slug="glyph-course")
    user = _registered_learner(course)
    attempt = form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat, crocodile)

    response = _results(logged_in_client, user, course)

    content = response.content.decode()
    your_answer = content.split('data-testid="learner-answer-')[1].split(
        'data-testid="correct-answer-'
    )[0]
    assert your_answer.count("Marked correct") == 2
    assert your_answer.count("Marked incorrect") == 1
    # The answer as a whole is still wrong; the verdict moves to the question.
    assert "Marked wrong" in content


@pytest.mark.django_db
def test_a_stale_stored_score_is_explained(mock_site_context, logged_in_client):
    """A score frozen under the old marking contradicts the review list below it."""
    form, question, dolphin, bat, crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Legacy Course", slug="legacy-course")
    user = _registered_learner(course)
    attempt = form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        # What ticking every option scored before checkbox marking became exact.
        scores={"score": 1, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat, crocodile)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is True
    assert "not been re-marked" in response.content.decode()


@pytest.mark.django_db
def test_a_current_score_carries_no_stale_score_note(
    mock_site_context, logged_in_client
):
    """An attempt scored under the current rules has nothing to explain away."""
    form, question, dolphin, bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Current Course", slug="current-course")
    user = _registered_learner(course)
    attempt = form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is False
    assert "not been re-marked" not in response.content.decode()


@pytest.mark.django_db
def test_a_changed_question_count_is_explained(mock_site_context, logged_in_client):
    """A quiz that lost a question shows a stale percentage the score alone cannot catch."""
    form, question, dolphin, bat, _crocodile = _checkbox_quiz()
    course = course_with_form(form, title="Shrunk Course", slug="shrunk-course")
    user = _registered_learner(course)
    attempt = form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        # 1 of 2 when it was sat; the second question has since been removed, so
        # the same answers score 1 of 1 today — right score, wrong total.
        scores={"score": 1, "max_score": 2},
    )
    answer = QuestionAnswerFactory(form_progress=attempt, question=question)
    answer.selected_options.add(dolphin, bat)

    response = _results(logged_in_client, user, course)

    assert response.context["stored_score_outdated"] is True
    assert "not been re-marked" in response.content.decode()


@pytest.mark.django_db
def test_a_completed_survey_does_not_promise_marking(
    mock_site_context, logged_in_client
):
    """Nothing marks a CATEGORY_VALUE_SUM form, so the page must not say marking is coming."""
    form = FormFactory(
        title="Confidence Survey", strategy=FormStrategy.CATEGORY_VALUE_SUM
    )
    course = course_with_form(form, title="Survey Course", slug="survey-course")
    user = _registered_learner(course)
    form_attempt(course, user, form, completed_time=timezone.now(), scores={})

    content = _results(logged_in_client, user, course).content.decode()

    assert "marking is in progress" not in content
    assert "being reviewed" not in content
    assert "Confidence Survey" in content


# Tests for form_start_page_buttons function.


@pytest.mark.django_db
def test_not_started_form_shows_start_button(mock_site_context):
    """When user hasn't started the form, show Start button."""
    UserFactory()
    form = FormFactory()
    buttons = form_start_page_buttons(
        form=form,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.none(),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Start Form"
    assert buttons[0]["action"] == "start"


@pytest.mark.django_db
def test_started_form_shows_continue_button(mock_site_context):
    """When user has started but not completed the form, show Continue button."""
    form = FormFactory()
    incomplete_progress: FormProgress = FormProgressFactory(form=form)

    buttons = form_start_page_buttons(
        form=form,
        incomplete_form_progress=incomplete_progress,
        completed_form_progress=FormProgress.objects.none(),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Continue Form"
    assert buttons[0]["action"] == "continue"


@pytest.mark.django_db
def test_completed_non_quiz_not_last_shows_next_button(mock_site_context):
    """When user completed a non-quiz form (not last item), show Next button."""
    form = FormFactory()
    completed_progress: FormProgress = FormProgressFactory(
        form=form, completed_time=timezone.now()
    )

    buttons = form_start_page_buttons(
        form=form,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Next"
    assert buttons[0]["action"] == "next"


@pytest.mark.django_db
def test_completed_non_quiz_last_shows_finish_course_button(
    mock_site_context,
):
    """When user completed a non-quiz form (last item), show Finish Course button."""
    form = FormFactory()
    completed_progress: FormProgress = FormProgressFactory(
        form=form, completed_time=timezone.now()
    )

    buttons = form_start_page_buttons(
        form=form,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=True,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Finish Course"
    assert buttons[0]["action"] == "finish_course"


@pytest.mark.django_db
def test_passed_quiz_not_last_shows_next_button(mock_site_context):
    """When user passed a quiz (not last item), show Next button."""
    # Create a quiz form
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=80
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )
    QuestionOptionFactory(question=question, text="4", correct=True, order=0)

    # Create completed progress with passing score
    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},  # 100% pass
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Next"
    assert buttons[0]["action"] == "next"


@pytest.mark.django_db
def test_passed_quiz_last_shows_finish_course_button(mock_site_context):
    """When user passed a quiz (last item), show Finish Course button."""
    # Create a quiz form
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=80
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with passing score
    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1},  # 100% pass
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=True,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Finish Course"
    assert buttons[0]["action"] == "finish_course"


@pytest.mark.django_db
def test_failed_quiz_shows_try_again_button(mock_site_context):
    """When user failed a quiz, show Try Again button (no Next button)."""
    # Create a quiz form
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=80
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with failing score
    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},  # 0% fail
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Try Again"
    assert buttons[0]["action"] == "try_again"


@pytest.mark.django_db
def test_failed_quiz_last_item_shows_only_try_again(mock_site_context):
    """When user failed a quiz (even if last item), show only Try Again button."""
    # Create a quiz form
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=80
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with failing score
    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1},  # 0% fail
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=True,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Try Again"
    assert buttons[0]["action"] == "try_again"


@pytest.mark.django_db
def test_quiz_passed_against_its_own_pass_mark_shows_next(mock_site_context):
    """A quiz is judged against its own pass mark, not a fixed threshold."""
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=50
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 3, "max_score": 5},  # 60%, over the 50% pass mark
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Next"
    assert buttons[0]["action"] == "next"


@pytest.mark.django_db
def test_quiz_failed_against_a_high_pass_mark_shows_try_again(mock_site_context):
    """A score under a strict pass mark offers a retry, not a way forward.

    The start page and ``get_content_status`` have to agree: an item the course
    index locks must not be reachable from a button on the page before it.
    """
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=90
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 17, "max_score": 20},  # 85%, under the 90% pass mark
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Try Again"
    assert buttons[0]["action"] == "try_again"


@pytest.mark.django_db
def test_quiz_with_no_pass_mark_shows_next(mock_site_context):
    """A quiz with no pass mark has nothing to fail, so the learner moves on."""
    quiz = FormFactory(
        title="Test Quiz", strategy=FormStrategy.QUIZ, quiz_pass_percentage=None
    )
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    completed_progress: FormProgress = FormProgressFactory(
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 2},
    )

    buttons = form_start_page_buttons(
        form=quiz,
        incomplete_form_progress=None,
        completed_form_progress=FormProgress.objects.filter(id=completed_progress.id),
        is_last_item=False,
    )

    assert len(buttons) == 1
    assert buttons[0]["text"] == "Next"
    assert buttons[0]["action"] == "next"


# The quiz runner must let a learner tell a single-select question from a
# multi-select one before they answer it. Under exact-set scoring a misread
# multi-select scores zero, so the distinction is not decorative.


def _runner_page(client, question_type):
    """Render page 1 of a one-question quiz of the given question type."""
    user = UserFactory()
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    question = FormQuestionFactory(form_page=page, type=question_type, order=0)
    QuestionOptionFactory(question=question, text="Alpha", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Beta", correct=False, order=1)

    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    return client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )


@pytest.mark.django_db
def test_multiple_choice_options_render_a_radio_indicator(mock_site_context, client):
    response = _runner_page(client, "multiple_choice")

    assert b'data-testid="radio-indicator"' in response.content
    assert b'data-testid="checkbox-indicator"' not in response.content


@pytest.mark.django_db
def test_checkbox_options_render_a_checkbox_indicator(mock_site_context, client):
    response = _runner_page(client, "checkboxes")

    assert b'data-testid="checkbox-indicator"' in response.content
    assert b'data-testid="radio-indicator"' not in response.content


@pytest.mark.django_db
def test_checkbox_question_carries_a_select_all_that_apply_hint(
    mock_site_context, client
):
    response = _runner_page(client, "checkboxes")

    assert "Select all that apply." in response.content.decode()


@pytest.mark.django_db
def test_multiple_choice_question_carries_no_select_all_hint(mock_site_context, client):
    response = _runner_page(client, "multiple_choice")

    assert "Select all that apply." not in response.content.decode()


# A completed QUIZ form with no ``quiz_pass_percentage`` set is a supported
# authoring configuration (a survey / self-assessment with a score but no
# verdict) and must never raise. Covers the status calculation in
# ``get_content_status`` plus the three views that build the outline through it:
# the course player, the results page, and the dashboard.


@pytest.fixture
def completed_quiz_no_pass_mark(mock_site_context):
    """A registered learner who has completed a QUIZ form with no pass mark set."""
    form = FormFactory(
        title="Ungraded Quiz",
        strategy=FormStrategy.QUIZ,
        quiz_pass_percentage=None,
    )
    course = course_with_form(
        form, title="No Pass Mark Course", slug="no-pass-mark-course"
    )
    user = UserFactory()
    LearnerCourseRegistrationFactory(learner__user=user, course=course, is_active=True)
    form_attempt(
        course,
        user,
        form,
        completed_time=timezone.now(),
        scores={"score": 3, "max_score": 5},
    )
    return {"course": course, "form": form, "user": user}


@pytest.mark.django_db
def test_get_course_index_quiz_without_pass_mark_reads_complete_ready(
    completed_quiz_no_pass_mark,
):
    """No pass mark to fail against: a completed attempt reads COMPLETE, not FAILED."""
    children = get_course_index(
        user=completed_quiz_no_pass_mark["user"],
        course=completed_quiz_no_pass_mark["course"],
        can_access_content=True,
    )
    statuses = [c["status"] for c in children]
    assert statuses == ["COMPLETE"]


def _results_page(fixture, logged_in_client):
    client = logged_in_client(fixture["user"])
    return client.get(
        reverse(
            "learner_interface:course_form_complete",
            kwargs={"course_slug": fixture["course"].slug, "index": 1},
        )
    )


@pytest.mark.django_db
def test_results_page_without_pass_mark_announces_no_verdict(
    completed_quiz_no_pass_mark, logged_in_client
):
    """No pass mark means no bar to clear, so the page claims neither outcome."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert "Quiz passed" not in content
    assert "Quiz not passed" not in content


@pytest.mark.django_db
def test_results_page_without_pass_mark_still_shows_the_score(
    completed_quiz_no_pass_mark, logged_in_client
):
    """Dropping the verdict must not drop the score: 3 of 5 is still reported."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert response.context["percentage"] == 60
    assert 'data-testid="quiz-score"' in content


@pytest.mark.django_db
def test_results_page_without_pass_mark_offers_continue_not_retry(
    completed_quiz_no_pass_mark, logged_in_client
):
    """A quiz nobody can fail cannot be "retried" — the only action is to move on."""
    response = _results_page(completed_quiz_no_pass_mark, logged_in_client)

    content = response.content.decode()
    assert "Retry quiz" not in content
    assert "Continue" in content


# A question legend has to hold the number, the question and the required
# asterisk on the right lines: the number beside the question's first line, the
# asterisk glued to its last word, and a two-paragraph question rendered as two
# paragraphs rather than run together into one.


def _legend_html(client, question_text: str, *, required: bool = True) -> str:
    """Render a one-question runner page and return just its <legend> markup."""
    form = FormFactory(title="Legend form")
    page = FormPageFactory(form=form, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page,
        question=question_text,
        type="long_text",
        required=required,
        order=0,
    )

    user = UserFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    response = client.get(
        reverse(
            "learner_interface:form_fill_page",
            kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
        )
    )
    assert response.status_code == 200

    legend = re.search(r"<legend\b.*?</legend>", response.content.decode(), re.DOTALL)
    assert legend is not None, "the runner page rendered no legend"
    return legend.group(0)


@pytest.mark.django_db
def test_a_two_paragraph_question_keeps_its_paragraphs_apart(mock_site_context, client):
    """Inlining every paragraph ran them together with no separator between them."""
    legend = _legend_html(client, "First paragraph.\n\nSecond paragraph.")

    assert legend.count("<p>") == 2
    # Only the last paragraph is inlined, so the first keeps its own line.
    assert "[&>p:last-of-type]:inline" in legend
    assert "[&>p]:inline" not in legend


@pytest.mark.django_db
def test_the_required_asterisk_is_the_last_thing_in_the_legend(
    mock_site_context, client
):
    """The asterisk trails the question's final paragraph, so it cannot wrap alone."""
    legend = _legend_html(client, "First paragraph.\n\nSecond paragraph.")

    tail = legend[legend.rindex("</p>") :]
    assert "&nbsp;" in tail
    assert 'data-testid="required-indicator-1"' in tail
    assert "(required)" in tail


@pytest.mark.django_db
def test_a_question_that_is_not_required_carries_no_asterisk(mock_site_context, client):
    legend = _legend_html(client, "Just the one paragraph.", required=False)

    assert "required-indicator" not in legend
    assert "(required)" not in legend


# Required questions must actually be required. Submitting a runner page with a
# required question left blank re-renders the page with an error instead of
# advancing to the next page or completing (and scoring) the attempt.


def _question_with_options(page, *, question_type, order, required=True):
    question = FormQuestionFactory(
        form_page=page, type=question_type, order=order, required=required
    )
    QuestionOptionFactory(question=question, text="Alpha", correct=True, order=0)
    QuestionOptionFactory(question=question, text="Beta", correct=False, order=1)
    return question


def _start_form(client, form):
    """Register a learner for a course holding `form` and start an attempt."""
    user = UserFactory()
    course = course_with_form(form)
    register_user_for_course(course, user)
    client.force_login(user)
    client.get(
        reverse(
            "learner_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )
    return user, course


def _page_url(course, page_number):
    return reverse(
        "learner_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": page_number},
    )


def _single_page_quiz():
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    answered = _question_with_options(page, question_type="multiple_choice", order=0)
    blank = _question_with_options(page, question_type="checkboxes", order=1)
    return form, answered, blank


@pytest.mark.django_db
def test_final_page_with_blank_required_question_returns_422(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    _user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert response.status_code == 422


@pytest.mark.django_db
def test_final_page_with_blank_required_question_does_not_complete_the_attempt(
    mock_site_context, client
):
    form, answered, _blank = _single_page_quiz()
    user, course = _start_form(client, form)

    client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert (
        CourseFormAttempt.objects.filter(
            course_progress=course_progress_record(course, user),
            collection_item=collection_item_for(course, form),
            form_progress__completed_time__isnull=False,
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_blank_required_question_is_reported_to_the_learner(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    _user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    assert b'data-testid="required-answers-error"' in response.content


@pytest.mark.django_db
def test_blank_required_question_leaves_no_answer_row_behind(mock_site_context, client):
    form, answered, _blank = _single_page_quiz()
    user, course = _start_form(client, form)

    client.post(
        _page_url(course, 1),
        {f"question_{answered.id}": str(answered.options.first().id)},
    )

    form_progress = get_latest_incomplete(
        course_progress_record(course, user), collection_item_for(course, form)
    )
    assert form_progress is not None
    assert list(form_progress.answers.values_list("question_id", flat=True)) == [
        answered.id
    ]


@pytest.mark.django_db
def test_answering_every_required_question_completes_the_attempt(
    mock_site_context, client
):
    form, answered, blank = _single_page_quiz()
    user, course = _start_form(client, form)

    response = client.post(
        _page_url(course, 1),
        {
            f"question_{answered.id}": str(answered.options.first().id),
            f"question_{blank.id}": str(blank.options.first().id),
        },
    )

    assert response.status_code == 302
    assert CourseFormAttempt.objects.filter(
        course_progress=course_progress_record(course, user),
        collection_item=collection_item_for(course, form),
        form_progress__completed_time__isnull=False,
    ).exists()


@pytest.mark.django_db
def test_blank_required_question_does_not_advance_to_the_next_page(
    mock_site_context, client
):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page_1 = FormPageFactory(form=form, order=0)
    _question_with_options(page_1, question_type="multiple_choice", order=0)
    page_2 = FormPageFactory(form=form, order=1)
    _question_with_options(page_2, question_type="multiple_choice", order=0)
    _user, course = _start_form(client, form)

    response = client.post(_page_url(course, 1), {})

    assert response.status_code == 422


@pytest.mark.django_db
def test_optional_question_left_blank_still_advances(mock_site_context, client):
    form = FormFactory(strategy=FormStrategy.QUIZ, quiz_pass_percentage=70)
    page = FormPageFactory(form=form, order=0)
    _question_with_options(page, question_type="checkboxes", order=0, required=False)
    _user, course = _start_form(client, form)

    response = client.post(_page_url(course, 1), {})

    assert response.status_code == 302
