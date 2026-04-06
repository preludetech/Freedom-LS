import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from freedom_ls.feedback.factories import FeedbackFormFactory, FeedbackTriggerLogFactory


@pytest.mark.django_db
def test_feedback_form_unique_active_trigger_per_site(mock_site_context):
    """Only one active FeedbackForm per trigger_point per site."""
    FeedbackFormFactory(trigger_point="course_completed", is_active=True)
    with pytest.raises(IntegrityError):
        FeedbackFormFactory(trigger_point="course_completed", is_active=True)


@pytest.mark.django_db
def test_feedback_form_allows_inactive_duplicate(mock_site_context):
    """Multiple inactive forms for the same trigger_point are allowed."""
    FeedbackFormFactory(trigger_point="course_completed", is_active=True)
    FeedbackFormFactory(trigger_point="course_completed", is_active=False)


@pytest.mark.django_db
def test_feedback_form_clean_rejects_unknown_trigger(mock_site_context):
    """FeedbackForm.clean() rejects unknown trigger points."""
    form = FeedbackFormFactory(trigger_point="course_completed")
    form.trigger_point = "nonexistent_trigger"
    with pytest.raises(ValidationError) as exc_info:
        form.clean()
    assert "trigger_point" in exc_info.value.message_dict


@pytest.mark.django_db
def test_feedback_trigger_log_unique_constraint(mock_site_context):
    """Only one FeedbackTriggerLog per site + user + trigger_point."""
    log = FeedbackTriggerLogFactory(trigger_point="course_completed")
    with pytest.raises(IntegrityError):
        FeedbackTriggerLogFactory(user=log.user, trigger_point="course_completed")
