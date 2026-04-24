"""Pure read helpers for content-engine snapshots / walks.

These helpers are used by ``student_interface.xapi_events`` and
``student_progress.xapi_events`` to build the ``object_definition`` and
``context.extensions`` dicts that the generic
:func:`freedom_ls.experience_api.tracking.track` expects.

Design constraints:

- **No imports from** ``experience_api``. These helpers are plain reads
  against the content-engine models; introducing an edge back to
  ``experience_api`` would invert the layering.
- **No DB writes.** Every function returns a dict or a model instance.
- Use ``select_related`` / ``prefetch_related`` per CLAUDE.md where
  relationship-walking is needed.
"""

from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Form,
    FormQuestion,
    Topic,
)


def _content_type_label(instance: Any) -> str:
    """Return a short lowercase type label suitable for the ``_type`` column."""
    return type(instance).__name__.lower()


def snapshot_topic(topic: Topic) -> dict:
    """Build the ``ObjectDefinition`` dict for a Topic."""
    return {
        "topic_id": topic.id,
        "topic_slug": topic.slug,
        "topic_title": topic.title,
        "topic_type": "topic",
    }


def snapshot_form(form: Form) -> dict:
    """Build the ``ObjectDefinition`` dict for a Form."""
    question_count = FormQuestion.objects.filter(form_page__form=form).count()
    return {
        "form_id": form.id,
        "form_slug": form.slug,
        "form_title": form.title,
        "form_type": form.strategy,
        "question_count": question_count,
        "max_score": None,  # scoring strategies vary; None-safe for now.
    }


def snapshot_question(question: FormQuestion) -> dict:
    """Build the ``ObjectDefinition`` dict for a FormQuestion."""
    # Collect options if any exist on the question.
    options = None
    if hasattr(question, "options"):
        option_qs = question.options.all() if hasattr(question.options, "all") else []
        option_list = [
            {
                "id": str(opt.id),
                "label": getattr(opt, "text", "") or getattr(opt, "label", ""),
            }
            for opt in option_qs
        ]
        options = option_list or None
    # FormQuestion has no slug field — use its id as a stable identifier.
    slug = getattr(question, "slug", None) or str(question.id)
    return {
        "question_id": question.id,
        "question_slug": slug,
        "question_text": question.question[:512] if question.question else "",
        "question_type": question.type,
        "options": options,
    }


def snapshot_course(course: Course) -> dict:
    """Build the ``ObjectDefinition`` dict for a Course."""
    return {
        "course_id": course.id,
        "course_slug": course.slug,
        "course_title": course.title,
    }


# ---------------------------------------------------------------------------
# Relationship walks
#
# ``walk_*`` helpers look up the course/topic context for an inner object.
# They return ``None`` when the relationship is ambiguous (zero or multiple
# matches) so the caller can decide how to handle it.


def walk_topic_to_course(topic: Topic) -> Course | None:
    """Find the unique course that contains ``topic``.

    Topics are hung off courses via ``ContentCollectionItem`` — directly or
    via a ``CoursePart`` intermediate. Returns the unique owning Course, or
    ``None`` when there is either no match or more than one match.
    """
    topic_ct = ContentType.objects.get_for_model(Topic)
    items = ContentCollectionItem.objects.filter(
        child_type=topic_ct, child_id=topic.id
    ).select_related("collection_type")

    candidates: list[Course] = []
    for item in items:
        collection = item.collection
        if isinstance(collection, Course):
            candidates.append(collection)
        elif isinstance(collection, CoursePart):
            parent = walk_course_part_to_course(collection)
            if parent is not None:
                candidates.append(parent)
    # Dedup by id.
    unique = {c.id: c for c in candidates}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def walk_course_part_to_course(course_part: CoursePart) -> Course | None:
    """Find the unique Course that contains ``course_part``."""
    part_ct = ContentType.objects.get_for_model(CoursePart)
    items = ContentCollectionItem.objects.filter(
        child_type=part_ct, child_id=course_part.id
    )
    candidates: list[Course] = []
    for item in items:
        collection = item.collection
        if isinstance(collection, Course):
            candidates.append(collection)
    unique = {c.id: c for c in candidates}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def walk_form_to_course(form: Form) -> Course | None:
    """Find the unique Course that contains ``form``."""
    form_ct = ContentType.objects.get_for_model(Form)
    items = ContentCollectionItem.objects.filter(child_type=form_ct, child_id=form.id)
    candidates: list[Course] = []
    for item in items:
        collection = item.collection
        if isinstance(collection, Course):
            candidates.append(collection)
        elif isinstance(collection, CoursePart):
            parent = walk_course_part_to_course(collection)
            if parent is not None:
                candidates.append(parent)
    unique = {c.id: c for c in candidates}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def walk_form_to_topic(form: Form) -> Topic | None:
    """Find the parent Topic when a form is embedded in one.

    Forms may also live directly under a course. When the form is not
    embedded in a topic, returns ``None``.
    """
    form_ct = ContentType.objects.get_for_model(Form)
    items = ContentCollectionItem.objects.filter(child_type=form_ct, child_id=form.id)
    for item in items:
        collection = item.collection
        if isinstance(collection, Topic):
            return collection
    return None


def walk_question_to_form(question: FormQuestion) -> Form | None:
    """Walk from a question back to its owning Form."""
    try:
        return question.form_page.form
    except AttributeError:
        return None


def walk_question_position(question: FormQuestion) -> int:
    """Return the 1-indexed position of the question within its form."""
    try:
        number: int = question.question_number()
        return number
    except Exception:  # pragma: no cover — defensive, never expected.
        return 0
