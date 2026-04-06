import pytest

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.feedback.factories import (
    FeedbackDismissalFactory,
    FeedbackFormFactory,
    FeedbackResponseFactory,
    FeedbackTriggerLogFactory,
)
from freedom_ls.feedback.models import FeedbackTriggerLog
from freedom_ls.feedback.signals import feedback_trigger
from freedom_ls.site_aware_models.models import _thread_locals


def _make_request(
    rf: RequestFactory, user: object, session: dict | None = None
) -> object:
    """Create a request with site and session set up."""
    request = rf.get("/")
    request.user = user
    request.session = session if session is not None else {}
    request._cached_site = (
        _thread_locals.request._cached_site
        if hasattr(_thread_locals, "request")
        and hasattr(_thread_locals.request, "_cached_site")
        else Site.objects.get_current()
    )
    return request


def _send_trigger(
    request: object,
    user: object,
    context_object: object,
    trigger_point: str = "course_completed",
) -> None:
    """Helper to send a feedback trigger signal."""
    feedback_trigger.send(
        sender=trigger_point,
        user=user,
        context_object=context_object,
        request=request,
    )


@pytest.mark.django_db
def test_trigger_increments_log_count(
    mock_site_context: None, rf: RequestFactory
) -> None:
    """Sending the signal increments the FeedbackTriggerLog count."""
    user = UserFactory()
    course = CourseFactory()
    request = _make_request(rf, user)

    _send_trigger(request, user, course)

    log = FeedbackTriggerLog.objects.get(user=user, trigger_point="course_completed")
    assert log.count == 1

    _send_trigger(request, user, course)
    log.refresh_from_db()
    assert log.count == 2


@pytest.mark.django_db
def test_eligible_sets_session_data(
    mock_site_context: None, rf: RequestFactory
) -> None:
    """When all eligibility checks pass, pending_feedback is set in session."""
    user = UserFactory()
    course = CourseFactory()
    FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    request = _make_request(rf, user)

    _send_trigger(request, user, course)

    assert "pending_feedback" in request.session
    assert "form_id" in request.session["pending_feedback"]


@pytest.mark.django_db
def test_min_occurrences_not_met(mock_site_context: None, rf: RequestFactory) -> None:
    """No session data when min_occurrences is not met."""
    user = UserFactory()
    course = CourseFactory()
    FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=3
    )

    request = _make_request(rf, user)

    _send_trigger(request, user, course)

    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_already_responded_for_same_object(
    mock_site_context: None, rf: RequestFactory
) -> None:
    """No session data when user already responded for the same context object."""
    user = UserFactory()
    course = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    ct = ContentType.objects.get_for_model(course)
    FeedbackResponseFactory(
        form=form, user=user, content_type=ct, object_id=str(course.pk)
    )

    # Need count >= 1, so create a log entry
    FeedbackTriggerLogFactory(user=user, trigger_point="course_completed", count=1)

    request = _make_request(rf, user)

    _send_trigger(request, user, course)

    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_three_dismissals_blocks_feedback(
    mock_site_context: None, rf: RequestFactory
) -> None:
    """No session data when user has dismissed 3+ times."""
    user = UserFactory()
    course = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    for _ in range(3):
        FeedbackDismissalFactory(form=form, user=user)

    request = _make_request(rf, user)

    _send_trigger(request, user, course)

    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_session_flag_blocks_feedback(
    mock_site_context: None, rf: RequestFactory
) -> None:
    """No session data when feedback_shown_this_session is already set."""
    user = UserFactory()
    course = CourseFactory()
    FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    request = _make_request(rf, user, session={"feedback_shown_this_session": True})

    _send_trigger(request, user, course)

    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_cooldown_not_elapsed(mock_site_context: None, rf: RequestFactory) -> None:
    """No session data when cooldown period has not elapsed."""
    user = UserFactory()
    course = CourseFactory()
    course2 = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed",
        is_active=True,
        min_occurrences=1,
        cooldown_days=30,
    )

    ct = ContentType.objects.get_for_model(course)
    # Create a recent response for a DIFFERENT object (same form, same user)
    FeedbackResponseFactory(
        form=form, user=user, content_type=ct, object_id=str(course.pk)
    )

    request = _make_request(rf, user)

    _send_trigger(request, user, course2)

    assert "pending_feedback" not in request.session
