import pytest

from django.contrib.contenttypes.models import ContentType
from django.test import Client

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.feedback.factories import FeedbackFormFactory
from freedom_ls.feedback.models import FeedbackDismissal, FeedbackResponse


@pytest.mark.django_db
def test_feedback_form_view_returns_html(mock_site_context, client: Client):
    """Test feedback form view returns form HTML."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    session = client.session
    session["pending_feedback"] = {
        "form_id": str(form.id),
        "content_type_id": ct.id,
        "object_id": str(course.pk),
    }
    session.save()

    response = client.get(
        f"/feedback/form/{form.id}/?content_type_id={ct.id}&object_id={course.pk}"
    )
    assert response.status_code == 200
    assert b"Submit Feedback" in response.content


@pytest.mark.django_db
def test_feedback_form_view_clears_session(mock_site_context, client: Client):
    """Test feedback form view clears pending_feedback from session."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    session = client.session
    session["pending_feedback"] = {
        "form_id": str(form.id),
        "content_type_id": ct.id,
        "object_id": str(course.pk),
    }
    session.save()

    client.get(
        f"/feedback/form/{form.id}/?content_type_id={ct.id}&object_id={course.pk}"
    )

    session = client.session
    assert "pending_feedback" not in session
    assert session["feedback_shown_this_session"] is True


@pytest.mark.django_db
def test_submit_creates_feedback_response(mock_site_context, client: Client):
    """Test submit creates FeedbackResponse with correct data."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    response = client.post(
        f"/feedback/submit/{form.id}/",
        {
            "rating": "4",
            "comment": "Great!",
            "content_type_id": ct.id,
            "object_id": str(course.pk),
        },
    )
    assert response.status_code == 200

    fb = FeedbackResponse.objects.get(form=form, user=user)
    assert fb.rating == 4
    assert fb.comment == "Great!"
    assert fb.object_id == str(course.pk)


@pytest.mark.django_db
def test_submit_returns_thank_you(mock_site_context, client: Client):
    """Test submit returns thank-you message."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory(thank_you_message="Thanks so much!")
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    response = client.post(
        f"/feedback/submit/{form.id}/",
        {
            "rating": "5",
            "content_type_id": ct.id,
            "object_id": str(course.pk),
        },
    )
    assert b"Thanks so much!" in response.content


@pytest.mark.django_db
def test_submit_invalid_rating(mock_site_context, client: Client):
    """Test submit rejects invalid rating."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    response = client.post(
        f"/feedback/submit/{form.id}/",
        {
            "rating": "0",
            "content_type_id": ct.id,
            "object_id": str(course.pk),
        },
    )
    assert response.status_code == 422


@pytest.mark.django_db
def test_dismiss_creates_dismissal(mock_site_context, client: Client):
    """Test dismiss creates FeedbackDismissal."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    response = client.post(
        f"/feedback/dismiss/{form.id}/",
        {"content_type_id": ct.id, "object_id": str(course.pk)},
    )
    assert response.status_code == 204
    assert FeedbackDismissal.objects.filter(form=form, user=user).exists()


@pytest.mark.django_db
def test_dismiss_returns_204(mock_site_context, client: Client):
    """Test dismiss returns HTTP 204."""
    user = UserFactory()
    client.force_login(user)
    form = FeedbackFormFactory()
    course = CourseFactory()
    ct = ContentType.objects.get_for_model(course)

    response = client.post(
        f"/feedback/dismiss/{form.id}/",
        {"content_type_id": ct.id, "object_id": str(course.pk)},
    )
    assert response.status_code == 204


@pytest.mark.django_db
def test_views_require_login(mock_site_context, client: Client):
    """Test all views require login."""
    form = FeedbackFormFactory()

    response = client.get(f"/feedback/form/{form.id}/")
    assert response.status_code == 302

    response = client.post(f"/feedback/submit/{form.id}/")
    assert response.status_code == 302

    response = client.post(f"/feedback/dismiss/{form.id}/")
    assert response.status_code == 302
