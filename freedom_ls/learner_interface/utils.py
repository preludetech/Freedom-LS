from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from freedom_ls.content_engine.models import (
    ContentCollectionItem,
    Course,
    CoursePart,
    Topic,
)
from freedom_ls.form_engine.models import Form, FormProgress, FormStrategy
from freedom_ls.form_engine.queries import quiz_verdict
from freedom_ls.learner_management.config import config
from freedom_ls.learner_management.deadline_utils import (
    EffectiveDeadline,
    get_course_deadlines,
)
from freedom_ls.learner_management.models import RecommendedCourse
from freedom_ls.learner_management.queries import is_registered_for_course_expression
from freedom_ls.learner_progress.models import (
    CourseFormAttempt,
    CourseProgress,
    TopicProgress,
)
from freedom_ls.learner_progress.queries import (
    completed_collection_item_ids,
    completed_form_item_ids,
    course_progress_by_course_for,
    course_progress_for,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.course_access.backends import AccessBadge

    type RequestUser = User | AnonymousUser | AbstractBaseUser


class Unresolved:
    """Marker for "the caller has not resolved this", not "there is none".

    Lets an optional course-progress argument tell a caller that already holds
    the record apart from one that has established there is no record at all.
    """


UNRESOLVED = Unresolved()

# Status constants
BLOCKED = "BLOCKED"
READY = "READY"
IN_PROGRESS = "IN_PROGRESS"
COMPLETE = "COMPLETE"
FAILED = "FAILED"


def derive_part_status(child_statuses: list[str]) -> str:
    """Summarise a course part from the statuses of the children it holds.

    Single source of the status-precedence rule for a part row, shared by the
    table of contents (``create_child_dict_with_flattened_index``) and
    ``get_content_status``. A part says what its own children say: while any
    one of them is open, a part with finished work behind it is under way, so
    a part can never read "not started" over rows that read "completed".

    A re-sit outranks that, because "needs retry" names the thing to do next
    where "in progress" only says work remains.

    "Under way" needs a child that can actually be opened. Once everything
    left is blocked -- a hard deadline that has expired, say -- the part is
    blocked too, however much of it is already finished: a part cannot report
    work in flight over rows the learner has no way back into.

    Which child the row links to is a separate question the caller answers.
    Every status but COMPLETE and BLOCKED guarantees an open child for it to
    route to, so the two can no longer contradict each other.
    """
    if not child_statuses:
        return BLOCKED
    if all(status == COMPLETE for status in child_statuses):
        return COMPLETE
    if IN_PROGRESS in child_statuses:
        return IN_PROGRESS
    if FAILED in child_statuses:
        return FAILED
    if READY in child_statuses:
        return IN_PROGRESS if COMPLETE in child_statuses else READY
    return BLOCKED


class CourseListingStatus(StrEnum):
    NOT_REGISTERED = "not_registered"
    REGISTERED = "registered"  # registered, 0%, not complete
    IN_PROGRESS = "in_progress"  # registered, >0%, completed_time is None
    COMPLETE = "complete"  # registered, completed_time is not None
    COMING_SOON = (
        "coming_soon"  # visibility == COMING_SOON; precedes registration status
    )


@dataclass(frozen=True)
class CourseListingEntry:
    course: Course
    status: CourseListingStatus
    progress_percentage: int
    access_badge: AccessBadge | None = None


def derive_listing_status(
    *,
    is_registered: bool,
    is_coming_soon: bool,
    is_complete: bool,
    progress_percentage: int,
) -> CourseListingStatus:
    """Map a course's registration/progress signals to its listing status.

    Single source of the status-precedence rule shared by the all-courses
    catalogue (``get_course_listing``) and the dashboard cards
    (``views.dashboard``): coming-soon (for the unregistered) precedes
    registration, which precedes completion, which precedes the in-progress /
    registered split. A learner registered for a coming-soon course keeps their
    registration-derived status, mirroring how hidden courses treat registrants.
    """
    if is_coming_soon and not is_registered:
        return CourseListingStatus.COMING_SOON
    if not is_registered:
        return CourseListingStatus.NOT_REGISTERED
    if is_complete:
        return CourseListingStatus.COMPLETE
    if progress_percentage > 0:
        return CourseListingStatus.IN_PROGRESS
    return CourseListingStatus.REGISTERED


def stamp_course_access_badge(course: Course, *, badge: AccessBadge | None) -> None:
    """Stamp the backend-owned access badge onto a course for template rendering.

    Shared by the all_courses catalogue and the dashboard discovery cards so the
    setattr lives in one place; templates read {{ course.access_badge.label }} /
    {{ course.access_badge.variant }} with no conditional branching. The badge
    itself comes from the active backend's get_access_badge — learner_interface
    never mints access-type copy.
    """
    setattr(course, "access_badge", badge)  # noqa: B010


@dataclass(frozen=True)
class FormPlacementProgress:
    """What the outline needs to know about one form placement in one record.

    ``is_complete`` is the shared rule -- the same sitting the stored percentage
    and the finish page count -- rather than a reading of whichever attempt was
    started last. The two flags beside it describe the sittings themselves, so
    the outline can still tell a re-sit in flight from one sat and failed.
    """

    is_complete: bool
    has_open_attempt: bool
    has_completed_attempt: bool


@dataclass(frozen=True)
class OutstandingItem:
    """A placement the learner still has to finish, and where it sits in the course."""

    index: int  # 1-based position in viewable_items(), which is what the player takes
    content: Topic | Form
    url: str
    is_retry: bool  # a quiz sat and failed, as against one not finished at all

    @property
    def is_form(self) -> bool:
        return isinstance(self.content, Form)

    @property
    def is_quiz(self) -> bool:
        return (
            isinstance(self.content, Form)
            and self.content.strategy == FormStrategy.QUIZ
        )


def outstanding_items(
    course_progress: CourseProgress, course: Course
) -> list[OutstandingItem]:
    """The placements in `course` this record has still to finish.

    A course is complete when every item in it is, so this lists the topics not
    yet completed alongside the quizzes not yet passed -- one never sat counts
    as much as one sat and failed. Used to withhold a course completion and to
    name what is left on the finish page.

    Scoped to one record and to this course's own placements, so a quiz failed
    in another course -- or under another registration -- cannot withhold this
    completion. Keyed on the placement, so passing one of two placements of the
    same quiz leaves the other listed.

    Counts the same placements the stored percentage counts and reads the same
    completion rows, so the finish page and the percentage beside it can never
    disagree about what is done.
    """
    completable = [
        (index, item)
        for index, item in enumerate(course.viewable_collection_items(), start=1)
        if item.child is not None and item.child.content_type in ("TOPIC", "FORM")
    ]
    if not completable:
        return []

    completed_item_ids = completed_collection_item_ids(course_progress)
    outstanding = [
        (index, item)
        for index, item in completable
        if item.id not in completed_item_ids
    ]
    if not outstanding:
        return []

    # A sitting that finished but did not pass is the one case the page can offer
    # as a retry; everything else is still to be started.
    sat_item_ids = set(
        CourseFormAttempt.objects.filter(
            course_progress=course_progress,
            collection_item_id__in=[item.id for _index, item in outstanding],
            form_progress__completed_time__isnull=False,
        ).values_list("collection_item_id", flat=True)
    )

    return [
        OutstandingItem(
            index=index,
            content=cast("Topic | Form", item.child),
            # form_start only for a re-sit, where the learner has already
            # committed to sitting the quiz once. It is a writing view -- it
            # mints an attempt on GET -- so offering it for a form never
            # started would let merely following the link and backing out
            # leave an empty attempt behind, which a submit-on-exit form later
            # finalises into a sitting the learner never took. Everything else
            # goes to the read-only start screen.
            url=reverse(
                "learner_interface:form_start"
                if item.id in sat_item_ids
                else "learner_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": index},
            ),
            is_retry=item.id in sat_item_ids,
        )
        for index, item in outstanding
    ]


def get_content_status(
    collection_item: ContentCollectionItem,
    next_status: str,
    topic_progress_map: dict[uuid.UUID, TopicProgress],
    form_placement_map: dict[uuid.UUID, FormPlacementProgress],
) -> tuple[str, str]:
    """
    Get the status for one placement based on the learner's progress.

    Progress is read from ``topic_progress_map`` / ``form_placement_map`` (keyed
    by collection item id), which the caller bulk-fetches once via
    ``_fetch_player_progress_maps`` so this runs without per-item queries.

    Returns tuple of (status, updated_next_status)
    """
    content_item = collection_item.child
    if isinstance(content_item, Topic):
        topic_progress = topic_progress_map.get(collection_item.id)

        if topic_progress and topic_progress.complete_time:
            return COMPLETE, READY
        elif topic_progress:
            return IN_PROGRESS, BLOCKED
        elif next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    elif isinstance(content_item, Form):
        placement = form_placement_map.get(collection_item.id)

        if placement and placement.is_complete:
            # Finished wins over a re-sit in flight: beginning another attempt at
            # a quiz already passed must not un-complete the placement, and must
            # not relock what the pass unlocked.
            return COMPLETE, READY
        elif placement and placement.has_open_attempt:
            return IN_PROGRESS, BLOCKED
        elif placement and placement.has_completed_attempt:
            # Sat, finished, and not complete: the deciding sitting failed.
            return FAILED, BLOCKED
        elif next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    elif isinstance(content_item, CoursePart):
        # For course parts, recursively check children's completion status.
        # collection_items(), not children(): the recursion reads the same
        # placement-keyed maps, so discarding the rows one level down would
        # silently read every nested item as "not started".
        part_items = content_item.collection_items()
        if not part_items:
            # Empty course part - treat as complete
            return COMPLETE, READY

        # Check the status of all children
        child_statuses = []
        temp_next_status = next_status

        for part_item in part_items:
            child_status, temp_next_status = get_content_status(
                part_item, temp_next_status, topic_progress_map, form_placement_map
            )
            child_statuses.append(child_status)

        part_status = derive_part_status(child_statuses)
        return part_status, READY if part_status == COMPLETE else BLOCKED

    else:
        # For courses, check if all direct children are complete
        # TODO: implement proper recursive course completion checking
        if next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED


def get_is_registered(user: RequestUser, course: Course) -> bool:
    """Check if user is registered for the course (directly or via cohort).

    Delegates to learner_management.utils.is_registered_for_course, which is the
    shared implementation also used by course_access.backends. Kept here as a thin
    wrapper so existing callers in learner_interface don't need to change.
    """
    from freedom_ls.learner_management.utils import is_registered_for_course

    return is_registered_for_course(user, course)


def get_course_registrations(user: RequestUser) -> list[Course]:
    """Get all courses a user is registered for (directly or via cohort)."""
    return list(
        Course.objects.annotate(
            _is_registered=is_registered_for_course_expression(user)
        ).filter(_is_registered=True)
    )


def get_resume_index(user: RequestUser, course: Course) -> int:
    """Return the 1-based index in ``course.viewable_items()`` to resume at.

    Reads the resume pointer off the record the learner's resolved registration
    names, so someone holding two records for one course comes back to where
    they left off under the registration they are studying through.

    Falls back to the first item when there is no record, nothing recorded, or
    the recorded placement is no longer viewable (deleted, unpublished, or
    removed from the course). Comparing placement ids means no FK resolve.
    """
    if not user.is_authenticated:
        return 1
    progress = course_progress_for(cast("User", user), course)
    if progress is None or progress.last_accessed_item_id is None:
        return 1
    index_by_collection_item_id = {
        item.id: n for n, item in enumerate(course.viewable_collection_items(), start=1)
    }
    return index_by_collection_item_id.get(progress.last_accessed_item_id, 1)


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
    course_progress: CourseProgress | None,
    viewable_collection_items: list[ContentCollectionItem],
) -> tuple[dict[uuid.UUID, TopicProgress], dict[uuid.UUID, FormPlacementProgress]]:
    """Bulk-fetch one record's progress for all viewable placements, in two queries.

    Returns (topic_progress_by_collection_item_id,
    form_placement_progress_by_collection_item_id). Both key on the **collection
    item**, not on the topic or form: one topic can be placed twice in a course
    and each placement is answered separately, so a content-keyed map would
    show both positions the same status.

    Which sitting decides a form placement is not settled here. The attempts are
    fetched once and handed to ``completed_form_item_ids``, the same rule the
    stored percentage and the finish page read, so the outline cannot come to a
    different view of what the learner has finished. What is settled here is only
    what that rule does not describe: whether there is a sitting in flight, and
    whether there has ever been a finished one.

    ``select_related("form_progress__form")`` so ``FormProgress.passed()`` reads
    ``form.quiz_pass_percentage`` / ``form.strategy`` without a per-quiz query.
    """
    topic_map: dict[uuid.UUID, TopicProgress] = {}
    form_map: dict[uuid.UUID, FormPlacementProgress] = {}
    if course_progress is None or not viewable_collection_items:
        return topic_map, form_map

    collection_item_ids = [item.id for item in viewable_collection_items]

    for tp in TopicProgress.objects.filter(
        course_progress=course_progress, collection_item_id__in=collection_item_ids
    ):
        topic_map[tp.collection_item_id] = tp

    attempts = list(
        CourseFormAttempt.objects.filter(
            course_progress=course_progress,
            collection_item_id__in=collection_item_ids,
        ).select_related("form_progress__form")
    )
    complete_item_ids = completed_form_item_ids(attempts)
    open_item_ids: set[uuid.UUID] = set()
    sat_item_ids: set[uuid.UUID] = set()
    for attempt in attempts:
        if attempt.form_progress.completed_time is None:
            open_item_ids.add(attempt.collection_item_id)
        else:
            sat_item_ids.add(attempt.collection_item_id)

    for collection_item_id in open_item_ids | sat_item_ids:
        form_map[collection_item_id] = FormPlacementProgress(
            is_complete=collection_item_id in complete_item_ids,
            has_open_attempt=collection_item_id in open_item_ids,
            has_completed_attempt=collection_item_id in sat_item_ids,
        )

    return topic_map, form_map


def get_course_index(
    user: RequestUser,
    course: Course,
    current_index: int | None = None,
    *,
    can_access_content: bool,
    course_progress: CourseProgress | None | Unresolved = UNRESOLVED,
) -> list[dict]:
    """
    Generate an index of course children with their status and metadata.

    ``can_access_content`` must be supplied by the caller from
    ``get_course_access_backend().get_access(...).can_access_content`` — the
    backend is never called here so that it runs once per request in the view
    layer. When False, all items are rendered as BLOCKED (no progress fetched).

    ``course_progress`` is the record the statuses are read from. A caller that
    has already resolved one passes it so the request does not resolve it
    twice; passing ``None`` means "there is no record", which is not the same
    as leaving it out.

    Returns a list of dictionaries with title, status, url, type, deadlines, and optionally children.
    """
    # Look up deadlines
    deadlines_map: dict[
        tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]
    ] = {}
    if user.is_authenticated and config.DEADLINES_ACTIVE:
        # is_authenticated guard above guarantees a real User here.
        deadlines_map = get_course_deadlines(cast("User", user), course)

    # Bulk-fetch per-item progress once (two queries) instead of one per item.
    # Only needed when the learner can access content: users without access get
    # forced-BLOCKED rows and get_content_status is never called.
    # can_access_content already implies an authenticated, registered user for
    # the default backend.
    topic_progress_map: dict[uuid.UUID, TopicProgress] = {}
    form_placement_map: dict[uuid.UUID, FormPlacementProgress] = {}
    if can_access_content and user.is_authenticated:
        if isinstance(course_progress, Unresolved):
            # can_access_content implies an authenticated, registered user (it
            # comes from the backend decision), so the cast to User is safe here.
            course_progress = course_progress_for(cast("User", user), course)
        topic_progress_map, form_placement_map = _fetch_player_progress_maps(
            course_progress, course.viewable_collection_items()
        )

    children = []
    next_status = READY  # First item starts as READY
    global_index = (
        0  # Running count of viewable items consumed (CourseParts are skipped)
    )

    for collection_item in course.collection_items():
        child_dict, next_status, items_added = create_child_dict_with_flattened_index(
            collection_item,
            course,
            global_index,
            next_status,
            can_access_content,
            topic_progress_map,
            form_placement_map,
            deadlines_map=deadlines_map,
            current_index=current_index,
        )
        children.append(child_dict)
        global_index += items_added

    return children


def current_entry_status(course_index: list[dict]) -> str | None:
    """Status of the row ``get_course_index`` marked ``is_current``, or None.

    Reading the status straight off the index the learner is shown is what stops
    the player's idea of "allowed" and the table of contents' idea of "Locked"
    from drifting apart again. Searches the top level and one level into a
    CoursePart's children, the only two places is_current is ever set.

    None means the index carried no current row, which callers must read as *not*
    blocked. Sequential unlock is a pedagogical gate, not a confidentiality one --
    the access backend owns that -- so an unexpected index shape must never strand
    a learner outside their own course.
    """
    for entry in course_index:
        if entry.get("is_current"):
            return cast("str", entry["status"])
        for child in entry.get("children", []):
            if child.get("is_current"):
                return cast("str", child["status"])
    return None


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
    collection_item: ContentCollectionItem,
    course: Course,
    start_index: int,
    next_status: str,
    can_access_content: bool,
    topic_progress_map: dict[uuid.UUID, TopicProgress],
    form_placement_map: dict[uuid.UUID, FormPlacementProgress],
    deadlines_map: dict[tuple[int | None, uuid.UUID | None], list[EffectiveDeadline]]
    | None = None,
    current_index: int | None = None,
) -> tuple[dict, str, int]:
    """
    Create a child dict with proper flattened indices for nested items.

    ``can_access_content`` drives item status: False → all items BLOCKED (no URLs);
    True → progress-aware status. The caller supplies this from the backend decision.

    When ``current_index`` (a 1-based viewable index) is supplied, the matching
    item dict is marked ``is_current=True`` and the containing CoursePart dict is
    marked ``contains_current=True`` so the TOC can highlight the current item
    and auto-expand its part.

    Returns tuple of (child_dict, updated_next_status, number_of_items_added)
    """
    if deadlines_map is None:
        deadlines_map = {}
    content_item = cast("Topic | Form | CoursePart", collection_item.child)

    # Handle CoursePart specially - don't calculate its status yet, process children first
    if isinstance(content_item, CoursePart):
        # CourseParts do not consume a URL slot in the viewable-only index space.
        items_added = 0
        part_items = content_item.collection_items()
        part_children_dicts = []
        part_next_status = next_status  # Use the incoming next_status for children

        # Calculate status and URL for each child of the CoursePart
        for part_item in part_items:
            part_child = cast("Topic | Form | CoursePart", part_item.child)
            if isinstance(part_child, CoursePart):
                # Defensive: today's data model does not nest parts; skip URL allocation
                # for any unexpected nested CoursePart and let status logic ignore it.
                continue
            if can_access_content:
                child_status, part_next_status = get_content_status(
                    part_item,
                    part_next_status,
                    topic_progress_map,
                    form_placement_map,
                )
                child_url = reverse(
                    "learner_interface:view_course_item",
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

        # Summarise the CoursePart, then pick where its row links to. These are
        # separate questions -- a part is labelled by everything its children
        # say, but routed to the one child the learner should open next -- so
        # taking the label off the routing branch would let a part row
        # contradict the rows beneath it. They stay in step all the same:
        # derive_part_status only reads "open" while some child is, which is
        # exactly when the chain below finds a url.
        status = derive_part_status([c["status"] for c in part_children_dicts])
        url = ""

        if part_children_dicts:
            # Resume-aware routing: the first IN_PROGRESS child (so a returning
            # learner lands where they left off), then the first READY child, then
            # the first child still needing a re-sit, then the first child once
            # everything is complete. BLOCKED children are never routed to, since
            # they carry no url of their own -- which is what a part whose first
            # child is hard-deadline-locked would otherwise link to.
            in_progress_child = next(
                (c for c in part_children_dicts if c["status"] == IN_PROGRESS), None
            )
            ready_child = next(
                (c for c in part_children_dicts if c["status"] == READY), None
            )
            failed_child = next(
                (c for c in part_children_dicts if c["status"] == FAILED), None
            )
            if in_progress_child:
                url = in_progress_child["url"]
            elif ready_child:
                url = ready_child["url"]
            elif failed_child:
                # The quiz itself stays reachable so it can be retried, and a part
                # row with no url would deny what its own child allows.
                url = failed_child["url"]
            elif status == COMPLETE:
                url = part_children_dicts[0]["url"]

        # CoursePart-level deadlines (from the CoursePart itself)
        part_deadlines = _get_deadlines_for_item(content_item, deadlines_map)

        child_dict = {
            "title": content_item.title,
            "status": status,
            "url": url or None,
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
        if can_access_content:
            status, next_status = get_content_status(
                collection_item, next_status, topic_progress_map, form_placement_map
            )
            url = reverse(
                "learner_interface:view_course_item",
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
        # A failed quiz offers only a retry: the item after it is BLOCKED, so a
        # Next button here would bounce the learner to the course detail page.
        if quiz_verdict(form, latest_completed) is False:
            buttons.append({"text": "Try Again", "action": "try_again"})
        elif is_last_item:
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
    """Get completed courses for a user. Returns empty list for anonymous users.

    Completion is read from the record the learner's resolved registration
    names. A learner holding two records for one course has finished it only if
    the one they are studying through says so, and the course is listed once
    either way.
    """
    if not user.is_authenticated:
        return []
    all_registered = get_course_registrations(user)
    if not all_registered:
        return []
    records = course_progress_by_course_for(cast("User", user), all_registered)
    return [
        course
        for course in all_registered
        if course.id in records and records[course.id].completed_time is not None
    ]


def get_current_courses(user: RequestUser) -> list[Course]:
    """Get current (in-progress) courses for a user. Returns empty list for anonymous users.

    The percentage stamped on each course comes from the resolved record, so a
    learner holding two records for one course sees the one they are studying
    through -- and sees the course once, not once per record.
    """
    if not user.is_authenticated:
        return []
    all_registered = get_course_registrations(user)
    if not all_registered:
        return []

    records = course_progress_by_course_for(cast("User", user), all_registered)

    current = []
    for course in all_registered:
        course_progress = records.get(course.id)

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


def get_form_for_index(
    course: Course, index: int, viewable_items: list | None = None
) -> Form:
    """Return the Form at the given 1-based index in a course's viewable items.

    Raises Http404 if the index is out of range or the item at that index is not a Form.
    Centralises the repeated index-validation guard from the form views.

    Pass ``viewable_items`` to reuse an already-fetched list (``viewable_items()``
    is not cached) — callers that also need the list themselves avoid a second query.
    """
    if viewable_items is None:
        viewable_items = course.viewable_items()
    if index < 1 or index > len(viewable_items):
        raise Http404("No course item at this index.")
    item = viewable_items[index - 1]
    if not isinstance(item, Form):
        raise Http404("Course item at this index is not a form.")
    return item


def get_form_collection_item_for_index(
    course: Course,
    index: int,
    viewable_collection_items: list[ContentCollectionItem] | None = None,
) -> ContentCollectionItem:
    """Return the collection item placing a Form at the given 1-based index.

    The form is ``.child``. Attempts key on the placement rather than on the
    form, because one form can be placed twice in a course and each placement
    is answered separately -- so the views that read or write attempts need
    the row, not just the form.

    Positionally identical to ``get_form_for_index``: both index into the same
    ordered sequence, and both raise the same Http404s.
    """
    if viewable_collection_items is None:
        viewable_collection_items = course.viewable_collection_items()
    if index < 1 or index > len(viewable_collection_items):
        raise Http404("No course item at this index.")
    collection_item = viewable_collection_items[index - 1]
    if not isinstance(collection_item.child, Form):
        raise Http404("Course item at this index is not a form.")
    return collection_item


def get_course_listing(
    user: RequestUser,
    visible_courses: QuerySet[Course] | None = None,
) -> list[CourseListingEntry]:
    """Build the all-courses listing for the learner interface.

    ``visible_courses`` may be passed by the caller (already filtered through
    ``backend.filter_visible``) to avoid a second queryset. When omitted, falls
    back to ``get_all_courses()`` — callers that don't need backend filtering
    (e.g. anonymous users) are unaffected.

    Returns one :class:`CourseListingEntry` per available course, pairing each
    course with the user's status and progress so the courses page can render
    every course in a single list regardless of registration state.

    The status of each entry is one of:

    - ``NOT_REGISTERED`` — the user is not registered for the course (always
      the case for anonymous users, who see every course at 0%).
    - ``REGISTERED`` — registered but no progress recorded yet (0%).
    - ``IN_PROGRESS`` — registered with some progress and not yet complete.
    - ``COMPLETE`` — registered and the course has a ``completed_time``.
    - ``COMING_SOON`` — the course is coming-soon and the learner is not registered
      for it (shows the express-interest affordance). Registered learners keep their
      registration-derived status, since coming-soon exempts already-registered users.

    ``access_badge`` on each entry comes from the access backend's config-only
    ``get_access_badge`` signal (one call per course, no per-user registration
    queries) — so the catalogue does not scale registration lookups with course
    count. The backend owns the badge copy; templates never call the backend.

    Used by the all-courses view (see ``views.py``) to populate the listing.
    """
    from freedom_ls.course_access.loader import get_course_access_backend
    from freedom_ls.course_access.overrides import is_coming_soon_for_display

    backend = get_course_access_backend()
    courses = visible_courses if visible_courses is not None else get_all_courses()

    if not user.is_authenticated:
        # The public catalogue passes a pre-filtered ``visible_courses`` queryset;
        # honour it verbatim. When a caller omits it, apply filter_visible to the
        # all-courses fallback so an anonymous listing never leaks hidden courses.
        anon_courses = (
            courses
            if visible_courses is not None
            else backend.filter_visible(user=user, courses=courses)
        )
        # Anonymous users are never registered, so coming-soon courses always show
        # the express-interest affordance (never an enrol link).
        return [
            CourseListingEntry(
                course,
                derive_listing_status(
                    is_registered=False,
                    is_coming_soon=is_coming_soon_for_display(course),
                    is_complete=False,
                    progress_percentage=0,
                ),
                0,
                access_badge=backend.get_access_badge(course=course),
            )
            for course in anon_courses
        ]
    registered_courses = get_course_registrations(user)
    registered_ids = {c.id for c in registered_courses}
    # Resolved per course, not merged across every record the account holds: a
    # learner studying one course through two organisations must see the
    # percentage of the registration they are actually studying through.
    records = course_progress_by_course_for(cast("User", user), registered_courses)

    entries: list[CourseListingEntry] = []
    for course in courses:
        access_badge = backend.get_access_badge(course=course)
        # records only holds registered courses, so unregistered / coming-soon
        # courses have no record and fall through to 0%. derive_listing_status owns
        # the precedence: coming-soon (for the unregistered) exempts already-registered
        # learners, mirroring hidden. (Hidden courses never reach here — filter_visible
        # drops them.)
        record = records.get(course.id)  # may be missing -> treat as 0%
        pct = record.progress_percentage if record else 0
        status = derive_listing_status(
            is_registered=course.id in registered_ids,
            is_coming_soon=is_coming_soon_for_display(course),
            is_complete=bool(record and record.completed_time is not None),
            progress_percentage=pct,
        )
        entries.append(CourseListingEntry(course, status, pct, access_badge))
    return entries
