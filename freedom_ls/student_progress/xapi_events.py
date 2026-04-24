"""xAPI event types emitted by ``student_progress``.

Owns ``(COMPLETED, Topic)`` and ``(PROGRESSED, Course)``. The
``(PROGRESSED, Course)`` schema carries the chaining fields
(``trigger_event_id`` and friends) that link the progression back to the
originating completion event — the chain is one level deep, never
recursive.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.content_engine.xapi_snapshots import (
    snapshot_course,
    snapshot_topic,
    walk_topic_to_course,
)
from freedom_ls.experience_api.models import Event
from freedom_ls.experience_api.registry import register_event_type
from freedom_ls.experience_api.schema_base import (
    SNAPSHOT_STRING_MAX_LENGTH,
    BaseEventSchema,
)
from freedom_ls.experience_api.tracking import track
from freedom_ls.experience_api.verbs import COMPLETED, PROGRESSED
from freedom_ls.student_management.xapi_snapshots import (
    resolve_cohort_for_user,
    resolve_user_course_registration,
)

# ---------------------------------------------------------------------------
# (COMPLETED, Topic)


class _CompletedTopicObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: UUID | None = None
    topic_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    topic_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _CompletedTopicResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion: bool
    duration: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    success: bool | None = None


class _CompletedTopicCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    cohort_id: UUID | None = None
    cohort_name: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    view_count: int = 0
    total_time_on_topic: str = Field(
        default="PT0S", max_length=SNAPSHOT_STRING_MAX_LENGTH
    )
    completion_source: str = Field(
        default="manual", max_length=SNAPSHOT_STRING_MAX_LENGTH
    )


class CompletedTopicSchema(BaseEventSchema):
    object_definition: _CompletedTopicObj
    result: _CompletedTopicResult
    context_extensions: _CompletedTopicCtx


register_event_type(COMPLETED, "Topic", CompletedTopicSchema)


def track_topic_completed(
    actor: User | None,
    topic: Topic,
    *,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    completion: bool = True,
    duration: str = "PT0S",
    success: bool | None = None,
    view_count: int = 0,
    total_time_on_topic: str = "PT0S",
    completion_source: str = "manual",
) -> Event | None:
    course = walk_topic_to_course(topic)
    registration = resolve_user_course_registration(actor, course)
    cohort = resolve_cohort_for_user(actor)
    return track(
        actor=actor,
        verb=COMPLETED,
        object_type="Topic",
        object_id=topic.id,
        object_definition=snapshot_topic(topic),
        result={
            "completion": completion,
            "duration": duration,
            "success": success,
        },
        context_extensions={
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else None,
            "registration_id": registration.id if registration else None,
            "view_count": view_count,
            "total_time_on_topic": total_time_on_topic,
            "completion_source": completion_source,
        },
        request=request,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# (PROGRESSED, Course)


class _ProgressedCourseObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _ProgressedCourseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion: bool
    # Inlined progress metrics — xAPI `result.extensions` is flattened here
    # into named fields so Pydantic validates them individually.
    progress_scaled: float
    progress_topics_completed: int
    progress_topics_total: int
    progress_forms_completed: int
    progress_forms_total: int


class _ProgressedCourseCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cohort_id: UUID | None = None
    cohort_name: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    trigger_event_id: UUID
    trigger_verb: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    trigger_object_type: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    trigger_object_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    trigger_object_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class ProgressedCourseSchema(BaseEventSchema):
    object_definition: _ProgressedCourseObj
    result: _ProgressedCourseResult
    context_extensions: _ProgressedCourseCtx


register_event_type(PROGRESSED, "Course", ProgressedCourseSchema)


def track_course_progressed(
    actor: User | None,
    course: Course,
    *,
    trigger_event: Event,
    completion: bool,
    progress_scaled: float,
    progress_topics_completed: int,
    progress_topics_total: int,
    progress_forms_completed: int,
    progress_forms_total: int,
    request: HttpRequest | None = None,
    strict: bool | None = None,
) -> Event | None:
    registration = resolve_user_course_registration(actor, course)
    cohort = resolve_cohort_for_user(actor)
    # Pull trigger metadata from the upstream event so the chain survives
    # independent of the trigger object's live state.
    trig_obj = trigger_event.object_definition or {}
    trig_slug = (
        trig_obj.get("topic_slug")
        or trig_obj.get("form_slug")
        or trig_obj.get("course_slug")
        or ""
    )
    trig_title = (
        trig_obj.get("topic_title")
        or trig_obj.get("form_title")
        or trig_obj.get("course_title")
        or ""
    )
    return track(
        actor=actor,
        verb=PROGRESSED,
        object_type="Course",
        object_id=course.id,
        object_definition=snapshot_course(course),
        result={
            "completion": completion,
            "progress_scaled": progress_scaled,
            "progress_topics_completed": progress_topics_completed,
            "progress_topics_total": progress_topics_total,
            "progress_forms_completed": progress_forms_completed,
            "progress_forms_total": progress_forms_total,
        },
        context_extensions={
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else "",
            "registration_id": registration.id if registration else None,
            "trigger_event_id": trigger_event.id,
            "trigger_verb": trigger_event.verb_display,
            "trigger_object_type": trigger_event.object_type,
            "trigger_object_slug": trig_slug,
            "trigger_object_title": trig_title,
        },
        request=request,
        strict=strict,
    )
