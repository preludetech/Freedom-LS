from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet
from django.urls import reverse
from django.utils import timezone

from freedom_ls.content_engine.models import (
    Course,
    CoursePart,
    Form,
    FormStrategy,
    Topic,
)
from freedom_ls.student_management.config import config
from freedom_ls.student_management.deadline_utils import (
    EffectiveDeadline,
    get_course_deadlines,
)
from freedom_ls.student_management.models import (
    CohortCourseRegistration,
    RecommendedCourse,
    UserCourseRegistration,
)
from freedom_ls.student_progress.models import (
    CourseProgress,
    FormProgress,
    TopicProgress,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User

    type RequestUser = User | AnonymousUser | AbstractBaseUser

# Status constants
BLOCKED = "BLOCKED"
READY = "READY"
IN_PROGRESS = "IN_PROGRESS"
COMPLETE = "COMPLETE"
FAILED = "FAILED"


class CourseListingStatus(StrEnum):
    NOT_REGISTERED = "not_registered"
    REGISTERED = "registered"  # registered, 0%, not complete
    IN_PROGRESS = "in_progress"  # registered, >0%, completed_time is None
    COMPLETE = "complete"  # registered, completed_time is not None


@dataclass(frozen=True)
class CourseListingEntry:
    course: Course
    status: CourseListingStatus
    progress_percentage: int


def get_content_status(
    content_item: Topic | Form | CoursePart | Course,
    user: User,
    next_status: str,
    topic_progress_map: dict[uuid.UUID, TopicProgress],
    form_progress_map: dict[uuid.UUID, FormProgress],
) -> tuple[str, str]:
    """
    Get the status for a content item based on user progress.

    Progress is read from ``topic_progress_map`` / ``form_progress_map`` (keyed
    by item id), which the caller bulk-fetches once via
    ``_fetch_player_progress_maps`` so this runs without per-item queries.

    Returns tuple of (status, updated_next_status)
    """
    if isinstance(content_item, Topic):
        topic_progress = topic_progress_map.get(content_item.id)

        if topic_progress and topic_progress.complete_time:
            return COMPLETE, READY
        elif topic_progress:
            return IN_PROGRESS, BLOCKED
        elif next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    elif isinstance(content_item, Form):
        form_progress = form_progress_map.get(content_item.id)

        if form_progress and form_progress.completed_time:
            if form_progress.form.strategy == FormStrategy.QUIZ:
                if form_progress.passed():
                    return COMPLETE, READY
                else:
                    return FAILED, BLOCKED
            else:
                return COMPLETE, READY
        elif form_progress:
            return IN_PROGRESS, BLOCKED
        elif next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    elif isinstance(content_item, CoursePart):
        # For course parts, recursively check children's completion status
        children = content_item.children()
        if not children:
            # Empty course part - treat as complete
            return COMPLETE, READY

        # Check the status of all children
        child_statuses = []
        temp_next_status = next_status

        for child in children:
            child_status, temp_next_status = get_content_status(
                child, user, temp_next_status, topic_progress_map, form_progress_map
            )
            child_statuses.append(child_status)

        # Determine CoursePart status based on children
        if IN_PROGRESS in child_statuses:
            return IN_PROGRESS, BLOCKED
        elif READY in child_statuses:
            return READY, BLOCKED
        elif all(s == COMPLETE for s in child_statuses):
            return COMPLETE, READY
        elif FAILED in child_statuses:
            return FAILED, BLOCKED
        else:
            return BLOCKED, BLOCKED

    else:
        # For courses, check if all direct children are complete
        # TODO: implement proper recursive course completion checking
        if next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED


def get_is_registered(user: RequestUser, course: Course) -> bool:
    """Check if user is registered for the course (directly or via cohort)."""
    if not user.is_authenticated:
        return False
    direct = UserCourseRegistration.objects.filter(
        user=user, collection=course, is_active=True
    ).exists()
    if direct:
        return True
    cohort = CohortCourseRegistration.objects.filter(
        cohort__cohortmembership__user=user, collection=course, is_active=True
    ).exists()
    return cohort


def get_course_registrations(user: RequestUser) -> list[Course]:
    """Get all courses a user is registered for (directly or via cohort)."""
    direct = UserCourseRegistration.objects.filter(
        user=user, is_active=True
    ).values_list("collection", flat=True)
    cohort = CohortCourseRegistration.objects.filter(
        cohort__cohortmembership__user=user, is_active=True
    ).values_list("collection", flat=True)
    return list(Course.objects.filter(Q(pk__in=direct) | Q(pk__in=cohort)).distinct())


def get_resume_index(user: RequestUser, course: Course) -> int:
    """Return the 1-based index in ``course.viewable_items()`` to resume at.

    Reads ``CourseProgress.last_accessed_item`` for ``(user, course)``. If there
    is no progress row, no recorded item, or the recorded item is no longer
    viewable (deleted / unpublished / removed from the course), falls back to the
    first item. One row fetch + one FK resolve — no per-item query loop.
    """
    if not user.is_authenticated:
        return 1
    progress = (
        CourseProgress.objects.filter(user=user, course=course)
        .select_related("last_accessed_content_type")
        .first()
    )
    if progress is None or progress.last_accessed_item is None:
        return 1
    item = progress.last_accessed_item
    index_by_key = {
        (type(i), i.pk): n for n, i in enumerate(course.viewable_items(), start=1)
    }
    return index_by_key.get((type(item), item.pk), 1)


def get_item_part(course: Course, current_item: Topic | Form) -> CoursePart | None:
    """Return the ``CoursePart`` that directly contains ``current_item``, or None.

    Walks ``course.children()`` once (the same traversal the index build uses)
    and checks each ``CoursePart``'s direct children in memory — no extra
    queries per item. Top-level items (not inside any part) return None.
    """
    for child in course.children():
        if isinstance(child, CoursePart):
            for part_child in child.children():
                if (
                    type(part_child) is type(current_item)
                    and part_child.pk == current_item.pk
                ):
                    return child
    return None


def _fetch_player_progress_maps(
    user: User,
    viewable_items: list[Topic | Form],
) -> tuple[dict[uuid.UUID, TopicProgress], dict[uuid.UUID, FormProgress]]:
    """Bulk-fetch this user's progress for all viewable items in two queries.

    Returns (topic_progress_by_id, latest_form_progress_by_id):
    - topic map keyed by topic_id -> TopicProgress (unique per user+topic)
    - form map keyed by form_id -> the user's LATEST FormProgress, first-seen
      under ``-start_time`` so it matches the old per-item
      ``.order_by("-start_time").first()`` semantics exactly. (The educator
      interface picks the latest *completed* attempt instead via
      ``F("completed_time").desc(nulls_last=True)``; that is a deliberately
      different behaviour, not adopted here.)

    ``select_related("form")`` so ``FormProgress.passed()`` reads
    ``form.quiz_pass_percentage`` / ``form.strategy`` without a per-quiz query.
    """
    topic_ids = [i.id for i in viewable_items if isinstance(i, Topic)]
    form_ids = [i.id for i in viewable_items if isinstance(i, Form)]

    topic_map: dict[uuid.UUID, TopicProgress] = {}
    if topic_ids:
        for tp in TopicProgress.objects.filter(user=user, topic_id__in=topic_ids):
            topic_map[tp.topic_id] = tp

    form_map: dict[uuid.UUID, FormProgress] = {}
    if form_ids:
        for fp in (
            FormProgress.objects.filter(user=user, form_id__in=form_ids)
            .select_related("form")
            .order_by("-start_time")
        ):
            if fp.form_id not in form_map:
                form_map[fp.form_id] = fp

    return topic_map, form_map


def get_course_index(
    user: User, course: Course, current_index: int | None = None
) -> list[dict]:
    """
    Generate an index of course children with their status and metadata.

    Returns a list of dictionaries with title, status, url, type, deadlines, and optionally children.
    """
    is_registered = get_is_registered(user, course)

    # Look up deadlines
    deadlines_map: dict[
        tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]
    ] = {}
    if user.is_authenticated and config.DEADLINES_ACTIVE:
        deadlines_map = get_course_deadlines(user, course)

    # Bulk-fetch per-item progress once (two queries) instead of one per item.
    # Only needed when registered: unregistered users get forced-BLOCKED rows
    # and get_content_status is never called. get_is_registered already implies
    # an authenticated user.
    topic_progress_map: dict[uuid.UUID, TopicProgress] = {}
    form_progress_map: dict[uuid.UUID, FormProgress] = {}
    if is_registered:
        topic_progress_map, form_progress_map = _fetch_player_progress_maps(
            user, course.viewable_items()
        )

    children = []
    next_status = READY  # First item starts as READY
    global_index = (
        0  # Running count of viewable items consumed (CourseParts are skipped)
    )

    for child in course.children():
        child_dict, next_status, items_added = create_child_dict_with_flattened_index(
            child,
            user,
            course,
            global_index,
            next_status,
            is_registered,
            topic_progress_map,
            form_progress_map,
            deadlines_map=deadlines_map,
            current_index=current_index,
        )
        children.append(child_dict)
        global_index += items_added

    return children


def _get_deadlines_for_item(
    content_item: Topic | Form | CoursePart,
    deadlines_map: dict[tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]],
) -> list[dict]:
    """Get deadline display dicts for a content item from the pre-fetched deadlines map."""
    if not deadlines_map:
        return []

    ct = ContentType.objects.get_for_model(content_item)
    key = (ct.id, content_item.pk)
    effective_deadlines = deadlines_map.get(key, [])

    # Fall back to course-level deadlines if no item-level ones
    if not effective_deadlines:
        effective_deadlines = deadlines_map.get((None, None), [])

    return [
        {
            "deadline": d.deadline,
            "is_hard_deadline": d.is_hard_deadline,
            "is_expired": d.deadline <= timezone.now(),
            "source": d.source,
        }
        for d in effective_deadlines
    ]


def _apply_deadline_locking(
    child_dict: dict,
    deadlines: list[dict],
) -> None:
    """Apply hard deadline locking to a child dict if needed."""
    if child_dict["status"] == COMPLETE:
        return

    hard_deadlines = [d for d in deadlines if d["is_hard_deadline"]]
    if not hard_deadlines:
        return

    # Most permissive (latest) hard deadline governs access
    most_permissive = max(hard_deadlines, key=lambda d: d["deadline"])
    if most_permissive["is_expired"]:
        child_dict["status"] = BLOCKED
        child_dict["url"] = None


def create_child_dict_with_flattened_index(
    content_item: Topic | Form | CoursePart,
    user: User,
    course: Course,
    start_index: int,
    next_status: str,
    is_registered: bool,
    topic_progress_map: dict[uuid.UUID, TopicProgress],
    form_progress_map: dict[uuid.UUID, FormProgress],
    deadlines_map: dict[tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]]
    | None = None,
    current_index: int | None = None,
) -> tuple[dict, str, int]:
    """
    Create a child dict with proper flattened indices for nested items.

    When ``current_index`` (a 1-based viewable index) is supplied, the matching
    item dict is marked ``is_current=True`` and the containing CoursePart dict is
    marked ``contains_current=True`` so the TOC can highlight the current item
    and auto-expand its part.

    Returns tuple of (child_dict, updated_next_status, number_of_items_added)
    """
    if deadlines_map is None:
        deadlines_map = {}

    # Handle CoursePart specially - don't calculate its status yet, process children first
    if isinstance(content_item, CoursePart):
        # CourseParts do not consume a URL slot in the viewable-only index space.
        items_added = 0
        part_children = content_item.children()
        part_children_dicts = []
        part_next_status = next_status  # Use the incoming next_status for children

        # Calculate status and URL for each child of the CoursePart
        for part_child in part_children:
            if isinstance(part_child, CoursePart):
                # Defensive: today's data model does not nest parts; skip URL allocation
                # for any unexpected nested CoursePart and let status logic ignore it.
                continue
            if is_registered:
                child_status, part_next_status = get_content_status(
                    part_child,
                    user,
                    part_next_status,
                    topic_progress_map,
                    form_progress_map,
                )
                child_url = reverse(
                    "student_interface:view_course_item",
                    kwargs={
                        "course_slug": course.slug,
                        "index": start_index + items_added + 1,
                    },
                )
            else:
                child_status = BLOCKED
                child_url = ""

            part_child_index = start_index + items_added + 1
            part_child_deadlines = _get_deadlines_for_item(part_child, deadlines_map)
            part_child_dict = {
                "title": part_child.title,
                "type": part_child.content_type,
                "url": child_url if child_status != BLOCKED else None,
                "status": child_status,
                "deadlines": part_child_deadlines,
                "is_current": current_index == part_child_index,
            }
            _apply_deadline_locking(part_child_dict, part_child_deadlines)
            part_children_dicts.append(part_child_dict)
            items_added += 1

        # Now calculate CoursePart's own status and URL based on children
        status = BLOCKED  # Default
        url = ""

        if part_children_dicts:
            # Resume-aware: route to the first IN_PROGRESS child (so a returning
            # student lands where they left off), then the first READY child, then
            # the first child if everything is complete. Skipping BLOCKED children
            # also avoids producing a row with status READY but url=None when the
            # first child is hard-deadline-locked.
            in_progress_child = next(
                (c for c in part_children_dicts if c["status"] == IN_PROGRESS), None
            )
            ready_child = next(
                (c for c in part_children_dicts if c["status"] == READY), None
            )
            if in_progress_child:
                status = IN_PROGRESS
                url = in_progress_child["url"]
            elif ready_child:
                status = READY
                url = ready_child["url"]
            elif all(c["status"] == COMPLETE for c in part_children_dicts):
                status = COMPLETE
                url = part_children_dicts[0]["url"]

        # CoursePart-level deadlines (from the CoursePart itself)
        part_deadlines = _get_deadlines_for_item(content_item, deadlines_map)

        child_dict = {
            "title": content_item.title,
            "status": status,
            "url": url if status != BLOCKED else None,
            "type": content_item.content_type,
            "children": part_children_dicts,
            "deadlines": part_deadlines,
            "contains_current": any(c.get("is_current") for c in part_children_dicts),
        }

        _apply_deadline_locking(child_dict, part_deadlines)

        # Update next_status based on the last child's processing
        next_status = part_next_status

    else:
        # Regular content item (Topic, Form, etc.)
        items_added = 1
        if is_registered:
            status, next_status = get_content_status(
                content_item, user, next_status, topic_progress_map, form_progress_map
            )
            url = reverse(
                "student_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": start_index + 1},
            )
        else:
            status = BLOCKED
            url = ""

        item_deadlines = _get_deadlines_for_item(content_item, deadlines_map)

        child_dict = {
            "title": content_item.title,
            "status": status,
            "url": url if status != BLOCKED else None,
            "type": content_item.content_type,
            "deadlines": item_deadlines,
            "is_current": current_index == start_index + 1,
        }

        _apply_deadline_locking(child_dict, item_deadlines)

    return child_dict, next_status, items_added


def form_start_page_buttons(
    form: Form,
    incomplete_form_progress: FormProgress | None,
    completed_form_progress: QuerySet[FormProgress],
    is_last_item: bool,
) -> list[dict[str, str]]:
    """
    Determine which buttons to show on the form start page.

    Returns a list of button dicts with 'text' and 'action' keys.
    """
    buttons = []

    # If user has incomplete progress, show Continue button
    if incomplete_form_progress:
        buttons.append({"text": "Continue Form", "action": "continue"})
        return buttons

    # Check if there's any completed progress
    latest_completed = completed_form_progress.first()

    if latest_completed:
        # For QUIZ forms, check if user passed
        if form.strategy == FormStrategy.QUIZ:
            scores = latest_completed.scores or {}
            score = scores.get("score", 0)
            max_score = scores.get("max_score", 1)

            # Calculate pass percentage (80% threshold)
            pass_threshold = 0.8
            percentage = score / max_score if max_score > 0 else 0
            passed = percentage >= pass_threshold

            if passed:
                # User passed the quiz
                if is_last_item:
                    buttons.append({"text": "Finish Course", "action": "finish_course"})
                else:
                    buttons.append({"text": "Next", "action": "next"})
            else:
                # User failed the quiz - only show Try Again
                buttons.append({"text": "Try Again", "action": "try_again"})
        else:
            # Non-quiz form that's completed
            if is_last_item:
                buttons.append({"text": "Finish Course", "action": "finish_course"})
            else:
                buttons.append({"text": "Next", "action": "next"})
    else:
        # No progress at all - show Start button
        buttons.append({"text": "Start Form", "action": "start"})

    return buttons


def get_all_courses() -> QuerySet[Course]:
    """Get all courses."""
    return Course.objects.all()


def get_completed_courses(user: RequestUser) -> list[Course]:
    """Get completed courses for a user. Returns empty list for anonymous users."""
    if not user.is_authenticated:
        return []
    all_registered = get_course_registrations(user)
    if not all_registered:
        return []
    completed_course_ids = set(
        CourseProgress.objects.filter(
            user=user,
            course__in=all_registered,
            completed_time__isnull=False,
        ).values_list("course_id", flat=True)
    )
    return [c for c in all_registered if c.id in completed_course_ids]


def get_current_courses(user: RequestUser) -> list[Course]:
    """Get current (in-progress) courses for a user. Returns empty list for anonymous users."""
    if not user.is_authenticated:
        return []
    all_registered = get_course_registrations(user)
    if not all_registered:
        return []

    # Fetch all course progress for this user in one query
    course_progress_dict = {
        cp.course_id: cp
        for cp in CourseProgress.objects.filter(
            user=user, course__in=all_registered
        ).select_related("course")
    }

    current = []
    for course in all_registered:
        course_progress = course_progress_dict.get(course.id)

        # Only include non-completed courses
        if course_progress and course_progress.completed_time:
            continue

        # Use the stored progress_percentage from CourseProgress
        percentage = course_progress.progress_percentage if course_progress else 0
        setattr(course, "progress_percentage", percentage)  # noqa: B010
        current.append(course)

    return current


def get_recommended_courses(user: RequestUser) -> QuerySet[RecommendedCourse]:
    """Get recommended courses for a user. Returns empty queryset for anonymous users."""
    if not user.is_authenticated:
        return RecommendedCourse.objects.none()
    return RecommendedCourse.objects.filter(user=user).select_related("collection")


def get_course_listing(user: RequestUser) -> list[CourseListingEntry]:
    """Build the all-courses listing for the student interface.

    Returns one :class:`CourseListingEntry` per available course, pairing each
    course with the user's status and progress so the courses page can render
    every course in a single list regardless of registration state.

    The status of each entry is one of:

    - ``NOT_REGISTERED`` — the user is not registered for the course (always
      the case for anonymous users, who see every course at 0%).
    - ``REGISTERED`` — registered but no progress recorded yet (0%).
    - ``IN_PROGRESS`` — registered with some progress and not yet complete.
    - ``COMPLETE`` — registered and the course has a ``completed_time``.

    Used by the all-courses view (see ``views.py``) to populate the listing.
    """
    if not user.is_authenticated:
        return [
            CourseListingEntry(course, CourseListingStatus.NOT_REGISTERED, 0)
            for course in get_all_courses()
        ]
    courses = get_all_courses()
    registered_ids = {c.id for c in get_course_registrations(user)}
    progress_rows = {
        row["course_id"]: row
        for row in CourseProgress.objects.filter(
            user=user, course__in=registered_ids
        ).values("course_id", "progress_percentage", "completed_time")
    }

    entries: list[CourseListingEntry] = []
    for course in courses:
        if course.id not in registered_ids:
            entries.append(
                CourseListingEntry(course, CourseListingStatus.NOT_REGISTERED, 0)
            )
            continue
        row = progress_rows.get(course.id)  # may be missing -> treat as 0%
        pct = row["progress_percentage"] if row else 0
        if row and row["completed_time"] is not None:
            status = CourseListingStatus.COMPLETE
        elif pct > 0:
            status = CourseListingStatus.IN_PROGRESS
        else:
            status = CourseListingStatus.REGISTERED
        entries.append(CourseListingEntry(course, status, pct))
    return entries
