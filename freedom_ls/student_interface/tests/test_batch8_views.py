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
    assert incomplete.completed_time is None

    assert response.status_code == 302
    expected_redirect = reverse(
        "student_interface:view_course_item",
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
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    client.get(
        reverse(
            "student_interface:form_start",
            kwargs={"course_slug": course.slug, "index": 1},
        )
    )

    # Persist page 1's answer.
    correct_option = questions[0].options.filter(correct=True).first()
    page1_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    client.post(page1_url, {f"question_{questions[0].id}": str(correct_option.id)})

    # On the final page, page 1's persisted answer is "another page" → base 1.
    page2_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 2},
    )
    assert client.get(page2_url).context["answered_other_pages"] == 1

    # Back on page 1, its own persisted answer is on the current page → base 0.
    assert client.get(page1_url).context["answered_other_pages"] == 0


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
    course = _make_course_with_form(form)
    _register(user, course)

    client.force_login(user)
    url = reverse(
        "student_interface:view_course_item",
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
    content = response.content.decode()
    expected_url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    # The "Leave and save" link must point at the real save-and-exit URL.
    assert f'href="{expected_url}"' in content
    # The unrendered template tag must not leak into the HTML (cotton would
    # otherwise pass the literal `{% url ... %}` through, HTML-escaped).
    assert "view_course_item" not in content.split("Leave and save")[0][-300:]
    assert "{% url" not in content


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
    # The quiz score ring (which surfaces a percentage) is only rendered for
    # QUIZ forms. The surrounding course chrome exposes its own course-progress
    # `percentage`, so assert on the rendered quiz element rather than the
    # aggregated template context.
    assert b'data-testid="quiz-percentage"' not in response.content


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


# ---------------------------------------------------------------------------
# Runner page rendering (QA report bug fixes)
# ---------------------------------------------------------------------------


def _start_runner(client, user, form):
    """Register the user, force-login, and GET the runner fill page (following
    the form_start redirect). Returns the rendered fill-page response."""
    course = _make_course_with_form(form)
    _register(user, course)
    client.force_login(user)
    start_url = reverse(
        "student_interface:form_start",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    return client.get(start_url, follow=True)


@pytest.mark.django_db
def test_runner_page_loads_content_engine_alpine_components(mock_site_context, client):
    """The runner must load content_engine's Alpine components.

    Regression (QA report bug 1): the runner base only loaded
    student_interface's Alpine components, so contentLightbox/onEscape were
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
    course = _make_course_with_form(form)
    _register(user, course)
    client.force_login(user)

    # No FormProgress created — POST straight to the fill page.
    page_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.post(page_url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "student_interface:view_course_item",
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
    course = _make_course_with_form(form)
    _register(user, course)
    client.force_login(user)

    # A completed attempt exists, so there is no incomplete attempt to resume.
    FormProgressFactory(
        user=user,
        form=form,
        completed_time=timezone.now(),
        scores={"score": 2, "max_score": 2},
    )

    page_url = reverse(
        "student_interface:form_fill_page",
        kwargs={"course_slug": course.slug, "index": 1, "page_number": 1},
    )
    response = client.get(page_url)

    assert response.status_code == 302
    expected_redirect = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    assert response["Location"] == expected_redirect


# ---------------------------------------------------------------------------
# Bug 2 — previous-attempts summary shows only the most-recent attempt
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_view_form_previous_attempts_limited_to_most_recent(mock_site_context, client):
    """The start-screen previous-attempts summary shows only the most-recent
    completed attempt, not every attempt (spec §86, plan §174/§298)."""
    user = UserFactory()
    form = _make_quiz_form()
    course = _make_course_with_form(form)
    _register(user, course)
    client.force_login(user)

    now = timezone.now()
    older = FormProgressFactory(
        user=user,
        form=form,
        completed_time=now - timezone.timedelta(hours=2),
        scores={"score": 0, "max_score": 2},
    )
    middle = FormProgressFactory(
        user=user,
        form=form,
        completed_time=now - timezone.timedelta(hours=1),
        scores={"score": 1, "max_score": 2},
    )
    most_recent = FormProgressFactory(
        user=user,
        form=form,
        completed_time=now,
        scores={"score": 2, "max_score": 2},
    )

    url = reverse(
        "student_interface:view_course_item",
        kwargs={"course_slug": course.slug, "index": 1},
    )
    response = client.get(url)

    assert response.status_code == 200
    completed = list(response.context["completed_form_progress"])
    assert completed == [most_recent]
    assert older not in completed
    assert middle not in completed
