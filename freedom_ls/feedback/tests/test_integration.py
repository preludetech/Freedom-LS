"""Integration tests for the feedback system end-to-end flows."""

import pytest

from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.feedback.factories import (
    FeedbackDismissalFactory,
    FeedbackFormFactory,
    FeedbackResponseFactory,
)
from freedom_ls.feedback.models import (
    FeedbackDismissal,
    FeedbackResponse,
    FeedbackTriggerLog,
)
from freedom_ls.feedback.registry import _registry, register_trigger_point
from freedom_ls.feedback.signals import feedback_trigger
from freedom_ls.site_aware_models.models import _thread_locals


def _make_request(rf: object, user: object, session: dict | None = None) -> object:
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
def test_full_page_load_flow(mock_site_context, rf):
    """Full page load flow: trigger sets session, session data has correct structure."""
    user = UserFactory()
    course = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    request = _make_request(rf, user)
    _send_trigger(request, user, course)

    pending = request.session.get("pending_feedback")
    assert pending is not None
    assert pending["form_id"] == str(form.id)
    ct = ContentType.objects.get_for_model(course)
    assert pending["content_type_id"] == ct.id
    assert pending["object_id"] == str(course.pk)


@pytest.mark.django_db
def test_htmx_flow_middleware_adds_trigger(mock_site_context, client: Client):
    """HTMX flow: pending_feedback in session causes HX-Trigger header."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()

    session = client.session
    session["pending_feedback"] = {
        "form_id": str(form.id),
        "content_type_id": 1,
        "object_id": "test-id",
    }
    session.save()

    # Make an HTMX request to any endpoint
    response = client.get("/health/", HTTP_HX_REQUEST="true")
    assert "HX-Trigger" in response


@pytest.mark.django_db
def test_submit_then_no_prompt_same_session(mock_site_context, rf):
    """After submitting feedback, no prompt appears in the same session."""
    user = UserFactory()
    course = CourseFactory()
    course2 = CourseFactory()
    FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )

    request = _make_request(rf, user)

    # First trigger sets pending_feedback
    _send_trigger(request, user, course)
    assert "pending_feedback" in request.session

    # Simulate user submitting feedback (sets session flag)
    request.session["feedback_shown_this_session"] = True
    request.session.pop("pending_feedback", None)

    # Second trigger in same session should not set pending_feedback
    _send_trigger(request, user, course2)
    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_cooldown_respected_across_sessions(mock_site_context, rf):
    """Cooldown prevents feedback prompt even in a new session."""
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
    FeedbackResponseFactory(
        form=form, user=user, content_type=ct, object_id=str(course.pk)
    )

    # New session (no feedback_shown_this_session flag)
    request = _make_request(rf, user)
    _send_trigger(request, user, course2)
    assert "pending_feedback" not in request.session


@pytest.mark.django_db
def test_three_dismissals_stop_showing(mock_site_context, rf):
    """After 3 dismissals, feedback form stops showing."""
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
def test_custom_trigger_point_full_flow(mock_site_context, rf):
    """Custom trigger points work through the full flow."""
    register_trigger_point("custom_test_trigger", "Test trigger")
    try:
        user = UserFactory()
        course = CourseFactory()
        FeedbackFormFactory(
            trigger_point="custom_test_trigger", is_active=True, min_occurrences=1
        )

        request = _make_request(rf, user)
        _send_trigger(request, user, course, trigger_point="custom_test_trigger")

        assert "pending_feedback" in request.session
        assert FeedbackTriggerLog.objects.filter(
            user=user, trigger_point="custom_test_trigger"
        ).exists()
    finally:
        del _registry["custom_test_trigger"]


@pytest.mark.django_db
def test_full_submit_flow_via_views(mock_site_context, client: Client):
    """End-to-end: trigger -> load form -> submit -> response saved."""
    user = UserFactory()
    client.force_login(user)
    course = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )
    ct = ContentType.objects.get_for_model(course)

    # Simulate trigger setting session
    session = client.session
    session["pending_feedback"] = {
        "form_id": str(form.id),
        "content_type_id": ct.id,
        "object_id": str(course.pk),
    }
    session.save()

    # Load feedback form
    response = client.get(
        f"/feedback/form/{form.id}/?content_type_id={ct.id}&object_id={course.pk}"
    )
    assert response.status_code == 200

    # Submit feedback
    response = client.post(
        f"/feedback/submit/{form.id}/",
        {
            "rating": "5",
            "comment": "Excellent course!",
            "content_type_id": ct.id,
            "object_id": str(course.pk),
        },
    )
    assert response.status_code == 200

    fb = FeedbackResponse.objects.get(form=form, user=user)
    assert fb.rating == 5
    assert fb.comment == "Excellent course!"


@pytest.mark.django_db
def test_full_dismiss_flow_via_views(mock_site_context, client: Client):
    """End-to-end: trigger -> load form -> dismiss -> dismissal saved."""
    user = UserFactory()
    client.force_login(user)
    course = CourseFactory()
    form = FeedbackFormFactory(
        trigger_point="course_completed", is_active=True, min_occurrences=1
    )
    ct = ContentType.objects.get_for_model(course)

    # Load and dismiss
    response = client.post(
        f"/feedback/dismiss/{form.id}/",
        {"content_type_id": ct.id, "object_id": str(course.pk)},
    )
    assert response.status_code == 204
    assert FeedbackDismissal.objects.filter(form=form, user=user).exists()
