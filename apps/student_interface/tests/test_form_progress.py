"""Tests for FormProgress model."""

from datetime import timedelta
import pytest
from django.utils import timezone

from content_engine.models import FormPage, FormQuestion, FormContent
from student_interface.models import FormProgress, QuestionAnswer


@pytest.mark.django_db
def test_get_current_page_number_no_answers(mock_site_context, user, form):
    """Test get_current_page_number when no questions are answered."""

    # Create pages with questions
    page1 = FormPage.objects.create(form=form, title="Page 1", order=0)
    page2 = FormPage.objects.create(form=form, title="Page 2", order=1)

    FormQuestion.objects.create(
        form_page=page1,
        question="Question 1",
        type="multiple_choice",
        order=0,
    )
    FormQuestion.objects.create(
        form_page=page2,
        question="Question 2",
        type="multiple_choice",
        order=0,
    )

    form_progress = FormProgress.objects.create(user=user, form=form)

    # Should return 1 (first page) since no questions are answered
    assert form_progress.get_current_page_number() == 1


@pytest.mark.django_db
def test_get_current_page_number_partially_answered(mock_site_context, user, form):
    """Test get_current_page_number when some questions are answered."""

    # Create pages with questions
    page1 = FormPage.objects.create(form=form, title="Page 1", order=0)
    page2 = FormPage.objects.create(form=form, title="Page 2", order=1)
    page3 = FormPage.objects.create(form=form, title="Page 3", order=2)

    question1 = FormQuestion.objects.create(
        form_page=page1, question="Question 1", type="short_text", order=0
    )
    FormQuestion.objects.create(
        form_page=page2, question="Question 2", type="short_text", order=0
    )
    FormQuestion.objects.create(
        form_page=page3, question="Question 3", type="short_text", order=0
    )

    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer questions on page 1
    QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1, text_answer="Answer 1"
    )

    # Should return 2 (second page) since page 1 is complete but page 2 is not
    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_current_page_number_all_answered(mock_site_context, user, form):
    """Test get_current_page_number when all questions are answered."""

    # Create pages with questions
    page1 = FormPage.objects.create(form=form, title="Page 1", order=0)
    page2 = FormPage.objects.create(form=form, title="Page 2", order=1)

    question1 = FormQuestion.objects.create(
        form_page=page1, question="Question 1", type="short_text", order=0
    )
    question2 = FormQuestion.objects.create(
        form_page=page2, question="Question 2", type="short_text", order=0
    )

    form_progress = FormProgress.objects.create(user=user, form=form)

    # Answer all questions
    QuestionAnswer.objects.create(
        form_progress=form_progress, question=question1, text_answer="Answer 1"
    )
    QuestionAnswer.objects.create(
        form_progress=form_progress, question=question2, text_answer="Answer 2"
    )

    # Should return 2 (last page) since all questions are answered
    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_current_page_number_page_with_text_only(mock_site_context, user, form):
    """Test get_current_page_number with pages that have only text (no questions)."""

    # Create pages - first has text, second has question
    page1 = FormPage.objects.create(form=form, title="Page 1", order=0)
    page2 = FormPage.objects.create(form=form, title="Page 2", order=1)

    # Page 1 has only text, no questions
    FormContent.objects.create(form_page=page1, content="Intro text", order=0)

    # Page 2 has a question
    FormQuestion.objects.create(
        form_page=page2, question="Question 2", type="short_text", order=0
    )

    form_progress = FormProgress.objects.create(user=user, form=form)

    # Should skip page 1 (no questions) and go to page 2
    assert form_progress.get_current_page_number() == 2


@pytest.mark.django_db
def test_get_or_create_incomplete_no_existing(mock_site_context, user, form):
    """Test get_or_create_incomplete when user has no existing progress."""

    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress is not None
    assert progress.user == user
    assert progress.form == form
    assert progress.completed_time is None
    assert FormProgress.objects.filter(user=user, form=form).count() == 1


@pytest.mark.django_db
def test_get_or_create_incomplete_returns_existing_incomplete(
    mock_site_context, user, form
):
    """Test get_or_create_incomplete returns existing incomplete progress."""

    # Create an incomplete progress
    existing = FormProgress.objects.create(user=user, form=form)

    # Should return the existing one
    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id == existing.id
    assert FormProgress.objects.filter(user=user, form=form).count() == 1


@pytest.mark.django_db
def test_get_or_create_incomplete_creates_new_when_completed(
    mock_site_context, user, form
):
    """Test get_or_create_incomplete creates new progress when existing is completed."""

    # Create a completed progress
    completed = FormProgress.objects.create(
        user=user, form=form, completed_time=timezone.now()
    )

    # Should create a new one
    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id != completed.id
    assert progress.completed_time is None
    assert FormProgress.objects.filter(user=user, form=form).count() == 2


@pytest.mark.django_db
def test_get_or_create_incomplete_returns_latest_incomplete(
    mock_site_context, user, form
):
    """Test get_or_create_incomplete returns the latest incomplete when multiple exist."""

    # Create an older incomplete progress
    older = FormProgress.objects.create(user=user, form=form)
    # Set the start_time to be older
    FormProgress.objects.filter(pk=older.pk).update(
        start_time=timezone.now() - timedelta(seconds=10)
    )

    # Create a newer incomplete progress
    newer = FormProgress.objects.create(user=user, form=form)

    # Should return the newer one
    progress = FormProgress.get_or_create_incomplete(user, form)

    assert progress.id == newer.id
    assert FormProgress.objects.filter(user=user, form=form).count() == 2
