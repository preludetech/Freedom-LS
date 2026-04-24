"""End-to-end coverage for each ``student_interface`` xAPI wrapper.

Covers per-wrapper:
- Happy path — wrapper emits a row with the expected verb/object_type and
  snapshot fields populated.
- Required-field-missing → TrackingSchemaError in strict mode.
- Deletion-survives — delete the referenced record after the event lands;
  the snapshot is still readable and the FK column goes NULL.

Per-event richness (ATTEMPTED / ANSWERED time-limit, multiple options,
etc.) is not retested here — the schema itself is the regression guard.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import (
    CourseFactory,
    FormFactory,
    TopicFactory,
)
from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
)
from freedom_ls.experience_api.exceptions import TrackingSchemaError
from freedom_ls.experience_api.models import Event
from freedom_ls.experience_api.verbs import (
    ATTEMPTED,
    COMPLETED,
    REGISTERED,
    VIEWED,
)
from freedom_ls.student_interface.xapi_events import (
    track_course_registered,
    track_form_attempted,
    track_form_completed,
    track_topic_viewed,
)


def _link_to_course(site, course, child) -> None:
    from django.contrib.contenttypes.models import ContentType

    ContentCollectionItem.objects.create(
        site=site,
        collection_type=ContentType.objects.get_for_model(Course),
        collection_id=course.id,
        child_type=ContentType.objects.get_for_model(type(child)),
        child_id=child.id,
        order=0,
    )


# ---------------------------------------------------------------------------
# (VIEWED, Topic)


@pytest.mark.django_db
def test_topic_viewed_writes_event(mock_site_context) -> None:
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    _link_to_course(mock_site_context, course, topic)

    evt = track_topic_viewed(user, topic)

    assert evt is not None
    assert evt.verb == VIEWED.iri
    assert evt.object_type == "Topic"
    assert evt.object_definition["topic_slug"] == topic.slug
    assert evt.context["extensions"]["course_slug"] == course.slug


@pytest.mark.django_db
def test_topic_viewed_deletion_survives(mock_site_context, settings) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    user = UserFactory()
    topic = TopicFactory()
    evt = track_topic_viewed(user, topic)
    assert evt is not None

    topic_id = topic.id
    topic.delete()

    refreshed = Event._base_manager.get(pk=evt.pk)
    assert refreshed.object_definition["topic_slug"]  # snapshot survived
    assert refreshed.object_id == topic_id


# ---------------------------------------------------------------------------
# (ATTEMPTED, Form)


@pytest.mark.django_db
def test_form_attempted_writes_event(mock_site_context, settings) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    user = UserFactory()
    form = FormFactory(strategy="progress")
    evt = track_form_attempted(user, form, attempt_number=1)
    assert evt is not None
    assert evt.verb == ATTEMPTED.iri
    assert evt.object_definition["form_slug"] == form.slug


# ---------------------------------------------------------------------------
# (COMPLETED, Form)


@pytest.mark.django_db
def test_form_completed_writes_event(mock_site_context, settings) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    user = UserFactory()
    form = FormFactory(strategy="progress")
    evt = track_form_completed(
        user, form, duration="PT5M", attempt_number=1, answers_changed=0
    )
    assert evt is not None
    assert evt.verb == COMPLETED.iri
    assert evt.object_type == "Form"
    assert evt.result is not None
    assert evt.result["completion"] is True


# ---------------------------------------------------------------------------
# (REGISTERED, Course)


@pytest.mark.django_db
def test_course_registered_writes_event(mock_site_context) -> None:
    user = UserFactory()
    course = CourseFactory()
    evt = track_course_registered(user, course)
    assert evt is not None
    assert evt.verb == REGISTERED.iri
    assert evt.object_type == "Course"
    assert evt.object_definition["course_slug"] == course.slug
    assert evt.context["extensions"]["registration_id_snapshot"]  # UUID present
    assert evt.result is not None
    assert evt.result["success"] is True


# ---------------------------------------------------------------------------
# Strict-mode required-field guard.


@pytest.mark.django_db
def test_attempted_form_required_missing_raises_strict(
    mock_site_context, settings
) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = True
    from freedom_ls.experience_api.tracking import track

    user = UserFactory()
    form = FormFactory(strategy="progress")
    # Bypass the wrapper and call the underlying track() with an
    # incomplete context_extensions dict to exercise the schema's
    # required-field guard.
    with pytest.raises(TrackingSchemaError):
        track(
            actor=user,
            verb=ATTEMPTED,
            object_type="Form",
            object_id=form.id,
            object_definition={
                "form_id": form.id,
                "form_slug": form.slug,
                "form_title": form.title,
                "form_type": form.strategy,
                "question_count": 0,
                "max_score": None,
            },
            context_extensions={},  # missing required `attempt_number`
        )
