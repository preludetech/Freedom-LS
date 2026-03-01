"""Tests for form_start_page_buttons function."""

import pytest

from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    FormFactory,
    FormPageFactory,
    FormQuestionFactory,
    QuestionOptionFactory,
)
from freedom_ls.content_engine.models import FormStrategy
from freedom_ls.student_interface.utils import form_start_page_buttons
from freedom_ls.student_progress.factories import FormProgressFactory
from freedom_ls.student_progress.models import FormProgress


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
    user = UserFactory()
    form = FormFactory()
    incomplete_progress: FormProgress = FormProgressFactory(user=user, form=form)

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
    user = UserFactory()
    form = FormFactory()
    completed_progress: FormProgress = FormProgressFactory(
        user=user, form=form, completed_time=timezone.now()
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
    user = UserFactory()
    form = FormFactory()
    completed_progress: FormProgress = FormProgressFactory(
        user=user, form=form, completed_time=timezone.now()
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
    user = UserFactory()
    # Create a quiz form
    quiz = FormFactory(title="Test Quiz", strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    question = FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )
    QuestionOptionFactory(question=question, text="4", correct=True, order=0)

    # Create completed progress with passing score
    completed_progress: FormProgress = FormProgressFactory(
        user=user,
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
    user = UserFactory()
    # Create a quiz form
    quiz = FormFactory(title="Test Quiz", strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with passing score
    completed_progress: FormProgress = FormProgressFactory(
        user=user,
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
    user = UserFactory()
    # Create a quiz form
    quiz = FormFactory(title="Test Quiz", strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with failing score
    completed_progress: FormProgress = FormProgressFactory(
        user=user,
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
    user = UserFactory()
    # Create a quiz form
    quiz = FormFactory(title="Test Quiz", strategy=FormStrategy.QUIZ)
    page = FormPageFactory(form=quiz, title="Page 1", order=0)
    FormQuestionFactory(
        form_page=page, question="What is 2+2?", type="multiple_choice", order=0
    )

    # Create completed progress with failing score
    completed_progress: FormProgress = FormProgressFactory(
        user=user,
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
