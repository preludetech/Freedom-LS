"""xAPI event types emitted by ``student_interface``.

Owns: ``(VIEWED, Topic)``, ``(ATTEMPTED, Form)``, ``(ANSWERED, Question)``,
``(COMPLETED, Form)``, ``(REGISTERED, Course)``.

Each event type has:

- A Pydantic schema subclassing :class:`BaseEventSchema` with three nested
  models (``_Obj`` / ``_Result`` / ``_Ctx``).
- A ``track_<object>_<verb>`` wrapper that builds the snapshot dicts from
  model instances and delegates to
  :func:`freedom_ls.experience_api.tracking.track`.
- A module-level ``register_event_type`` call that lands the schema in the
  registry at import time. ``student_interface.apps.py`` imports this
  module during ``ready()`` so the registrations fire on app load.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from django.http import HttpRequest

from freedom_ls.content_engine.models import Course, Form, FormQuestion, Topic
from freedom_ls.content_engine.xapi_snapshots import (
    snapshot_course,
    snapshot_form,
    snapshot_question,
    snapshot_topic,
    walk_form_to_course,
    walk_form_to_topic,
    walk_question_position,
    walk_question_to_form,
    walk_topic_to_course,
)
from freedom_ls.experience_api.models import Event
from freedom_ls.experience_api.registry import register_event_type
from freedom_ls.experience_api.schema_base import (
    RESULT_RESPONSE_MAX_LENGTH,
    SNAPSHOT_STRING_MAX_LENGTH,
    STRING_EXTENSION_MAX_LENGTH,
    BaseEventSchema,
)
from freedom_ls.experience_api.tracking import track
from freedom_ls.experience_api.verbs import (
    ANSWERED,
    ATTEMPTED,
    COMPLETED,
    REGISTERED,
    VIEWED,
)
from freedom_ls.student_management.models import Cohort, UserCourseRegistration
from freedom_ls.student_management.xapi_snapshots import (
    resolve_cohort_for_user,
    resolve_user_course_registration,
)

# ---------------------------------------------------------------------------
# (VIEWED, Topic)


class _ViewedTopicObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: UUID | None = None
    topic_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    topic_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    topic_type: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _ViewedTopicCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    cohort_id: UUID | None = None
    cohort_name: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    referrer: str | None = Field(default=None, max_length=STRING_EXTENSION_MAX_LENGTH)
    position_in_course: int | None = None


class ViewedTopicSchema(BaseEventSchema):
    object_definition: _ViewedTopicObj
    result: None = None
    context_extensions: _ViewedTopicCtx


register_event_type(VIEWED, "Topic", ViewedTopicSchema)


def track_topic_viewed(
    actor,
    topic: Topic,
    *,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    referrer: str | None = None,
    position_in_course: int | None = None,
    course: Course | None = None,
    cohort: Cohort | None = None,
    registration: UserCourseRegistration | None = None,
) -> Event | None:
    course = course or walk_topic_to_course(topic)
    registration = registration or resolve_user_course_registration(actor, course)
    cohort = cohort or resolve_cohort_for_user(actor)
    return track(
        actor=actor,
        verb=VIEWED,
        object_type="Topic",
        object_id=topic.id,
        object_definition=snapshot_topic(topic),
        context_extensions={
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else None,
            "registration_id": registration.id if registration else None,
            "referrer": referrer,
            "position_in_course": position_in_course,
        },
        request=request,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# (ATTEMPTED, Form)


class _AttemptedFormObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_id: UUID | None = None
    form_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    form_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    form_type: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    question_count: int
    max_score: int | None = None


class _AttemptedFormCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    cohort_id: UUID | None = None
    cohort_name: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    topic_id: UUID | None = None
    topic_slug: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    topic_title: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    attempt_number: int
    time_limit: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)


class AttemptedFormSchema(BaseEventSchema):
    object_definition: _AttemptedFormObj
    result: None = None
    context_extensions: _AttemptedFormCtx


register_event_type(ATTEMPTED, "Form", AttemptedFormSchema)


def track_form_attempted(
    actor,
    form: Form,
    *,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    attempt_number: int = 1,
    time_limit: str | None = None,
) -> Event | None:
    course = walk_form_to_course(form)
    topic = walk_form_to_topic(form)
    registration = resolve_user_course_registration(actor, course)
    cohort = resolve_cohort_for_user(actor)
    return track(
        actor=actor,
        verb=ATTEMPTED,
        object_type="Form",
        object_id=form.id,
        object_definition=snapshot_form(form),
        context_extensions={
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else None,
            "registration_id": registration.id if registration else None,
            "topic_id": topic.id if topic else None,
            "topic_slug": topic.slug if topic else None,
            "topic_title": topic.title if topic else None,
            "attempt_number": attempt_number,
            "time_limit": time_limit,
        },
        request=request,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# (ANSWERED, Question)


class _AnsweredQuestionObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: UUID | None = None
    question_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    question_text: str = Field(max_length=STRING_EXTENSION_MAX_LENGTH)
    question_type: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    options: list | None = Field(default=None)


class _AnsweredQuestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: str | list = Field(max_length=RESULT_RESPONSE_MAX_LENGTH)
    success: bool | None = None
    score_raw: int | None = None
    score_max: int | None = None
    duration: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _AnsweredQuestionCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    form_id: UUID | None = None
    form_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    form_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    form_attempt_id: UUID
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    cohort_id: UUID | None = None
    cohort_name: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    attempt_number: int
    question_position: int
    changed_answer: bool
    correct_answer: str | list | None = None


class AnsweredQuestionSchema(BaseEventSchema):
    object_definition: _AnsweredQuestionObj
    result: _AnsweredQuestionResult
    context_extensions: _AnsweredQuestionCtx


register_event_type(ANSWERED, "Question", AnsweredQuestionSchema)


def track_question_answered(
    actor,
    question: FormQuestion,
    *,
    form_attempt_id: UUID,
    attempt_number: int,
    response,
    duration: str,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    success: bool | None = None,
    score_raw: int | None = None,
    score_max: int | None = None,
    changed_answer: bool = False,
    correct_answer=None,
) -> Event | None:
    form = walk_question_to_form(question)
    course = walk_form_to_course(form) if form else None
    cohort = resolve_cohort_for_user(actor)
    question_position = walk_question_position(question)
    return track(
        actor=actor,
        verb=ANSWERED,
        object_type="Question",
        object_id=question.id,
        object_definition=snapshot_question(question),
        result={
            "response": response,
            "success": success,
            "score_raw": score_raw,
            "score_max": score_max,
            "duration": duration,
        },
        context_extensions={
            "form_id": form.id if form else None,
            "form_slug": form.slug if form else "",
            "form_title": form.title if form else "",
            "form_attempt_id": form_attempt_id,
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else None,
            "attempt_number": attempt_number,
            "question_position": question_position,
            "changed_answer": changed_answer,
            "correct_answer": correct_answer,
        },
        request=request,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# (COMPLETED, Form)


class _CompletedFormObj(_AttemptedFormObj):
    # Same shape as AttemptedForm.
    model_config = ConfigDict(extra="forbid")


class _CompletedFormResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion: bool
    success: bool | None
    score_raw: int | None
    score_max: int | None
    score_scaled: float | None = None
    duration: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    response: str | None = Field(default=None, max_length=RESULT_RESPONSE_MAX_LENGTH)


class _CompletedFormCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    cohort_id: UUID | None = None
    cohort_name: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    topic_id: UUID | None = None
    topic_slug: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    topic_title: str | None = Field(default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH)
    attempt_number: int
    pass_threshold: float | None = None
    answers_changed: int
    timed_out: bool


class CompletedFormSchema(BaseEventSchema):
    object_definition: _CompletedFormObj
    result: _CompletedFormResult
    context_extensions: _CompletedFormCtx


register_event_type(COMPLETED, "Form", CompletedFormSchema)


def track_form_completed(
    actor,
    form: Form,
    *,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    completion: bool = True,
    success: bool | None = None,
    score_raw: int | None = None,
    score_max: int | None = None,
    score_scaled: float | None = None,
    duration: str = "PT0S",
    response: str | None = None,
    attempt_number: int = 1,
    pass_threshold: float | None = None,
    answers_changed: int = 0,
    timed_out: bool = False,
) -> Event | None:
    course = walk_form_to_course(form)
    topic = walk_form_to_topic(form)
    registration = resolve_user_course_registration(actor, course)
    cohort = resolve_cohort_for_user(actor)
    return track(
        actor=actor,
        verb=COMPLETED,
        object_type="Form",
        object_id=form.id,
        object_definition=snapshot_form(form),
        result={
            "completion": completion,
            "success": success,
            "score_raw": score_raw,
            "score_max": score_max,
            "score_scaled": score_scaled,
            "duration": duration,
            "response": response,
        },
        context_extensions={
            "course_id": course.id if course else None,
            "course_slug": course.slug if course else "",
            "course_title": course.title if course else "",
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else None,
            "registration_id": registration.id if registration else None,
            "topic_id": topic.id if topic else None,
            "topic_slug": topic.slug if topic else None,
            "topic_title": topic.title if topic else None,
            "attempt_number": attempt_number,
            "pass_threshold": pass_threshold,
            "answers_changed": answers_changed,
            "timed_out": timed_out,
        },
        request=request,
        strict=strict,
    )


# ---------------------------------------------------------------------------
# (REGISTERED, Course)


class _RegisteredCourseObj(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: UUID | None = None
    course_slug: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    course_title: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)


class _RegisteredCourseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool


class _RegisteredCourseCtx(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cohort_id: UUID | None = None
    cohort_name: str = Field(default="", max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registration_id: UUID | None = None
    registration_id_snapshot: UUID
    registered_by: str = Field(max_length=SNAPSHOT_STRING_MAX_LENGTH)
    registered_by_user_id: UUID | None = None
    registered_by_email: str | None = Field(
        default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH
    )
    registered_by_display_name: str | None = Field(
        default=None, max_length=SNAPSHOT_STRING_MAX_LENGTH
    )
    start_date: str | None = None
    end_date: str | None = None


class RegisteredCourseSchema(BaseEventSchema):
    object_definition: _RegisteredCourseObj
    result: _RegisteredCourseResult
    context_extensions: _RegisteredCourseCtx


register_event_type(REGISTERED, "Course", RegisteredCourseSchema)


def track_course_registered(
    actor,
    course: Course,
    *,
    request: HttpRequest | None = None,
    strict: bool | None = None,
    registered_by: str = "self",
    registered_by_user=None,
    cohort: Cohort | None = None,
    registration: UserCourseRegistration | None = None,
    start_date=None,
    end_date=None,
) -> Event | None:
    from uuid import uuid4

    registration = registration or resolve_user_course_registration(actor, course)
    cohort = cohort or resolve_cohort_for_user(actor)
    # registration_id_snapshot is tracker-assigned and survives deletion of
    # the registration row.
    snapshot_id = registration.id if registration else uuid4()
    return track(
        actor=actor,
        verb=REGISTERED,
        object_type="Course",
        object_id=course.id,
        object_definition=snapshot_course(course),
        result={"success": True},
        context_extensions={
            "cohort_id": cohort.id if cohort else None,
            "cohort_name": cohort.name if cohort else "",
            "registration_id": registration.id if registration else None,
            "registration_id_snapshot": snapshot_id,
            "registered_by": registered_by,
            "registered_by_user_id": registered_by_user.id
            if registered_by_user
            else None,
            "registered_by_email": getattr(registered_by_user, "email", None),
            "registered_by_display_name": (
                getattr(registered_by_user, "display_name", None)
                or getattr(registered_by_user, "email", None)
            ),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        request=request,
        strict=strict,
    )
