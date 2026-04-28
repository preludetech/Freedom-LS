"""End-to-end coverage for each ``student_progress`` xAPI wrapper.

Includes the PROGRESSED-course chain test — the progression event must
carry the COMPLETED topic's id in ``trigger_event_id``.
"""

from __future__ import annotations

import pytest

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory, TopicFactory
from freedom_ls.experience_api.verbs import COMPLETED, PROGRESSED
from freedom_ls.student_progress.xapi_events import (
    track_course_progressed,
    track_topic_completed,
)


@pytest.mark.django_db
def test_topic_completed_writes_event(mock_site_context, settings) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    user = UserFactory()
    topic = TopicFactory()
    evt = track_topic_completed(user, topic, duration="PT30S", view_count=1)
    assert evt is not None
    assert evt.verb == COMPLETED.iri
    assert evt.object_type == "Topic"
    assert evt.result is not None
    assert evt.result["completion"] is True


@pytest.mark.django_db
def test_progressed_course_chains_trigger_event_id(mock_site_context, settings) -> None:
    settings.EXPERIENCE_API_STRICT_VALIDATION = False
    user = UserFactory()
    course = CourseFactory()
    topic = TopicFactory()
    completed = track_topic_completed(user, topic, duration="PT30S")
    assert completed is not None

    progressed = track_course_progressed(
        user,
        course,
        trigger_event=completed,
        completion=False,
        progress_scaled=0.5,
        progress_topics_completed=1,
        progress_topics_total=2,
        progress_forms_completed=0,
        progress_forms_total=0,
    )
    assert progressed is not None
    assert progressed.verb == PROGRESSED.iri
    assert progressed.object_type == "Course"
    assert progressed.context["extensions"]["trigger_event_id"] == str(completed.id)
    assert progressed.context["extensions"]["trigger_verb"] == "completed"
    assert progressed.context["extensions"]["trigger_object_type"] == "Topic"
    assert progressed.context["extensions"]["trigger_object_slug"] == topic.slug
