"""Resolving form attempts inside a course progress record.

`form_engine` answers "which attempt at this form is open for this user"; that
is the right question for a form sat on its own, and the wrong one here. A
learner holding two registrations for one course has two records, and an attempt
begun under one must never be resumed under the other -- so the course asks
"which attempt at this placement is open in this record", which only a
`CourseFormAttempt` can answer.

Every course-side caller goes through here, so an attempt is only ever resolved
against the record it was begun in. Nothing outside this module may resolve one
from `(user, form)`: that question cannot tell two records of the same course
apart, and it cannot tell a course attempt from a standalone one.
"""

from __future__ import annotations

from typing import cast

from django.db import transaction
from django.db.models import QuerySet

from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress


def get_latest_incomplete(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress | None:
    """The learner's open attempt at this placement in this record, if any."""
    course_attempt = (
        CourseFormAttempt.objects.filter(
            course_progress=course_progress,
            collection_item=collection_item,
            form_progress__completed_time__isnull=True,
        )
        .select_related("form_progress__form")
        .order_by("-form_progress__start_time")
        .first()
    )
    return course_attempt.form_progress if course_attempt else None


def latest_attempt(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress | None:
    """This record's most recent attempt at this placement, complete or not."""
    course_attempt = (
        CourseFormAttempt.objects.filter(
            course_progress=course_progress, collection_item=collection_item
        )
        .select_related("form_progress__form")
        .order_by("-form_progress__start_time")
        .first()
    )
    return course_attempt.form_progress if course_attempt else None


def ensure_attempt(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress:
    """This record's latest attempt at this placement, started if there is none.

    Unlike `get_or_create_incomplete`, a finished attempt satisfies this: the
    callers are seeding fixtures that need *an* attempt to hang answers off, not
    an open one to carry a learner forward.
    """
    return latest_attempt(course_progress, collection_item) or get_or_create_incomplete(
        course_progress, collection_item
    )


def get_or_create_incomplete(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress:
    """The learner's open attempt at this placement, or a fresh one.

    The attempt and its course side are written together: a `FormProgress` with
    no `CourseFormAttempt` reads as one sat outside a course, so a half-written
    pair would silently stop counting toward the record's percentage.
    """
    incomplete = get_latest_incomplete(course_progress, collection_item)
    if incomplete:
        return incomplete

    with transaction.atomic():
        attempt: FormProgress = FormProgress.objects.create(
            site_id=course_progress.site_id,
            user=course_progress.learner.user,
            form=collection_item.child,
        )
        CourseFormAttempt.objects.create(
            site_id=course_progress.site_id,
            course_progress=course_progress,
            collection_item=collection_item,
            form_progress=attempt,
        )
    return attempt


def finalise_stale_incomplete(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress | None:
    """For submit-on-exit forms: complete the learner's open attempt, if there is one.

    Safe for save-on-exit forms (no-op) and idempotent via complete().
    """
    form = cast("Form", collection_item.child)
    if not form.submit_on_exit:
        return None
    incomplete = get_latest_incomplete(course_progress, collection_item)
    if incomplete is None:
        return None
    incomplete.complete()
    return incomplete


def completed_attempts(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> QuerySet[FormProgress]:
    """This record's finished attempts at this placement, newest first.

    Filtered through the reverse one-to-one, so callers keep working in
    `FormProgress` -- what they actually read is the score and the verdict.
    `select_related("form")` because every caller reaches for
    `form.quiz_pass_percentage` to decide whether the attempt passed.
    """
    return (
        FormProgress.objects.filter(
            course_attempt__course_progress=course_progress,
            course_attempt__collection_item=collection_item,
            completed_time__isnull=False,
        )
        .select_related("form")
        .order_by("-completed_time")
    )
