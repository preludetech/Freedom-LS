"""Tests for form_start_page_buttons function."""

import pytest
from django.utils import timezone

from freedom_ls.content_engine.models import Form, FormPage, FormQuestion, QuestionOption, FormStrategy, Course
from freedom_ls.student_progress.models import FormProgress, QuestionAnswer
from freedom_ls.student_interface.utils import form_start_page_buttons


@pytest.mark.django_db
def test_not_started_form_shows_start_button(mock_site_context, user, form):
    """When user hasn't started the form, show Start button."""
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
def test_started_form_shows_continue_button(mock_site_context, user, form):
    """When user has started but not completed the form, show Continue button."""
    incomplete_progress = FormProgress.objects.create(user=user, form=form)

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
def test_completed_non_quiz_not_last_shows_next_button(mock_site_context, user, form):
    """When user completed a non-quiz form (not last item), show Next button."""
    completed_progress = FormProgress.objects.create(
        user=user,
        form=form,
        completed_time=timezone.now()
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
def test_completed_non_quiz_last_shows_finish_course_button(mock_site_context, user, form):
    """When user completed a non-quiz form (last item), show Finish Course button."""
    completed_progress = FormProgress.objects.create(
        user=user,
        form=form,
        completed_time=timezone.now()
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
def test_passed_quiz_not_last_shows_next_button(mock_site_context, user):
    """When user passed a quiz (not last item), show Next button."""
    # Create a quiz form
    quiz = Form.objects.create(
        title="Test Quiz",
        strategy=FormStrategy.QUIZ
    )
    page = FormPage.objects.create(form=quiz, title="Page 1", order=0)
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0
    )
    correct_option = QuestionOption.objects.create(
        question=question,
        text="4",
        correct=True,
        order=0
    )

    # Create completed progress with passing score
    completed_progress = FormProgress.objects.create(
        user=user,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1}  # 100% pass
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
def test_passed_quiz_last_shows_finish_course_button(mock_site_context, user):
    """When user passed a quiz (last item), show Finish Course button."""
    # Create a quiz form
    quiz = Form.objects.create(
        title="Test Quiz",
        strategy=FormStrategy.QUIZ
    )
    page = FormPage.objects.create(form=quiz, title="Page 1", order=0)
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0
    )

    # Create completed progress with passing score
    completed_progress = FormProgress.objects.create(
        user=user,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 1, "max_score": 1}  # 100% pass
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
def test_failed_quiz_shows_try_again_button(mock_site_context, user):
    """When user failed a quiz, show Try Again button (no Next button)."""
    # Create a quiz form
    quiz = Form.objects.create(
        title="Test Quiz",
        strategy=FormStrategy.QUIZ
    )
    page = FormPage.objects.create(form=quiz, title="Page 1", order=0)
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0
    )

    # Create completed progress with failing score
    completed_progress = FormProgress.objects.create(
        user=user,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1}  # 0% fail
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
def test_failed_quiz_last_item_shows_only_try_again(mock_site_context, user):
    """When user failed a quiz (even if last item), show only Try Again button."""
    # Create a quiz form
    quiz = Form.objects.create(
        title="Test Quiz",
        strategy=FormStrategy.QUIZ
    )
    page = FormPage.objects.create(form=quiz, title="Page 1", order=0)
    question = FormQuestion.objects.create(
        form_page=page,
        question="What is 2+2?",
        type="multiple_choice",
        order=0
    )

    # Create completed progress with failing score
    completed_progress = FormProgress.objects.create(
        user=user,
        form=quiz,
        completed_time=timezone.now(),
        scores={"score": 0, "max_score": 1}  # 0% fail
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
