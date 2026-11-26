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

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from freedom_ls.content_engine.models import ContentCollectionItem
from freedom_ls.form_engine.models import Form, FormDeclaration, FormProgress
from freedom_ls.learner_progress.models import CourseFormAttempt, CourseProgress

# A sitting opened this recently is reused by a second start rather than finalised:
# a double click or two tabs opened together belong to one sitting.
START_REUSE_WINDOW = timedelta(seconds=10)


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


def _open_sitting_unless_expired(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> FormProgress | None:
    """The open sitting at this placement, after completing it if its time has
    run out. Call it under the course progress lock."""
    sitting = get_latest_incomplete(course_progress, collection_item)
    if sitting is not None and sitting.complete_if_expired(timezone.now()):
        return None
    return sitting


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
    *,
    kept_if_untouched_since: datetime | None = None,
) -> FormProgress | None:
    """For submit-on-exit forms: complete the learner's open attempt, if there is one.

    An attempt last touched at or before `kept_if_untouched_since` was interrupted, not
    left, so it stays open for the learner to continue. Safe for save-on-exit forms
    (no-op) and idempotent via complete().
    """
    form = cast("Form", collection_item.child)
    if not form.submit_on_exit:
        return None
    incomplete = get_latest_incomplete(course_progress, collection_item)
    if incomplete is None:
        return None
    if (
        kept_if_untouched_since is not None
        and incomplete.last_updated_time <= kept_if_untouched_since
    ):
        return None
    incomplete.complete()
    return incomplete


def _kept_open(open_sitting: FormProgress, *, signing: bool) -> bool:
    """Whether a new start should carry on with this open sitting rather than
    finalise it: it is unanswered and either a double start or, when the
    learner is signing, not yet signed."""
    if open_sitting.answers.exists():
        return False
    if open_sitting.start_time >= timezone.now() - START_REUSE_WINDOW:
        return True
    # Nothing is served for an unsigned sitting until it is signed, so the
    # learner never left it; finalising it would leave an attempt with no
    # declaration.
    return (
        signing
        and not FormDeclaration.objects.filter(form_progress=open_sitting).exists()
    )


def close_left_signed_sitting(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
    *,
    kept_if_untouched_since: datetime | None = None,
) -> FormProgress | None:
    """The open sitting a declaration quiz should resume, after finalising one
    the learner left (submit-on-exit forms only).

    The counterpart of `start_attempt` for a start that signs nothing: it
    decides under the same lock, and by the same rules, whether the open
    sitting carries on. An unsigned sitting is never finalised here, since the
    learner is sent to sign it. Returns None when no sitting is left open.
    """
    with transaction.atomic():
        CourseProgress.objects.select_for_update().get(pk=course_progress.pk)
        open_sitting = _open_sitting_unless_expired(course_progress, collection_item)
        if open_sitting is None or _kept_open(open_sitting, signing=True):
            return open_sitting
        finalised = finalise_stale_incomplete(
            course_progress,
            collection_item,
            kept_if_untouched_since=kept_if_untouched_since,
        )
        return None if finalised is not None else open_sitting


def start_attempt(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
    *,
    kept_if_untouched_since: datetime | None = None,
    declaration: FormDeclaration | None = None,
) -> FormProgress:
    """Begin, or resume, the learner's sitting at this placement.

    Runs under a lock on the course progress row, so two starts for one record
    serialise instead of each finalising the other's brand-new sitting. An open
    sitting started within `START_REUSE_WINDOW` and not yet answered is reused
    untouched, since that is a double start; any other is finalised first for
    submit-on-exit forms (see `finalise_stale_incomplete`).

    `declaration` is an unsaved `FormDeclaration` with its text, typed name and
    IP address set. It is saved against the sitting returned, in the same
    transaction that creates or resumes it, unless that sitting is already
    signed. The lock is what stops two posts of one signature writing two rows.
    """
    with transaction.atomic():
        CourseProgress.objects.select_for_update().get(pk=course_progress.pk)
        open_sitting = _open_sitting_unless_expired(course_progress, collection_item)
        reusable = open_sitting is not None and _kept_open(
            open_sitting, signing=declaration is not None
        )
        if not reusable:
            finalise_stale_incomplete(
                course_progress,
                collection_item,
                kept_if_untouched_since=kept_if_untouched_since,
            )
        sitting = get_or_create_incomplete(course_progress, collection_item)
        if (
            declaration is not None
            and not FormDeclaration.objects.filter(form_progress=sitting).exists()
        ):
            declaration.form_progress = sitting
            # Set from the record, as get_or_create_incomplete does for the
            # sitting, so the declaration shares its sitting's site with no
            # request in scope.
            declaration.site_id = course_progress.site_id
            declaration.save()
        return sitting


@dataclass(frozen=True)
class SittingsAtPlacement:
    """Whether this record holds an open sitting, and a finished one, at a placement."""

    has_open: bool
    has_completed: bool


def sittings_at_placement(
    course_progress: CourseProgress,
    collection_item: ContentCollectionItem,
) -> SittingsAtPlacement:
    """Both flags from one query, for a caller that offers something for each: the open
    sitting can be submitted as it stands, the finished one has results to show."""
    completed_times = CourseFormAttempt.objects.filter(
        course_progress=course_progress, collection_item=collection_item
    ).values_list("form_progress__completed_time", flat=True)
    times = list(completed_times)
    return SittingsAtPlacement(
        has_open=any(time is None for time in times),
        has_completed=any(time is not None for time in times),
    )


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
