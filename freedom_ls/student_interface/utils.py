from django.urls import reverse
from django.utils import timezone
from freedom_ls.content_engine.models import (
    Topic,
    Form,
    Course,
    CoursePart,
    FormStrategy,
)
from django.db.models import QuerySet

from freedom_ls.student_progress.models import FormProgress, TopicProgress
from freedom_ls.student_management.models import Student, RecommendedCourse
from freedom_ls.student_management.deadline_utils import (
    get_course_deadlines,
    is_item_locked,
    EffectiveDeadline,
)

# Status constants
BLOCKED = "BLOCKED"
READY = "READY"
IN_PROGRESS = "IN_PROGRESS"
COMPLETE = "COMPLETE"
FAILED = "FAILED"


def get_content_status(content_item, user, next_status):
    """
    Get the status for a content item based on user progress.

    Returns tuple of (status, updated_next_status)
    """
    if isinstance(content_item, Topic):
        topic_progress = TopicProgress.objects.filter(
            user=user, topic=content_item
        ).first()

        if topic_progress and topic_progress.complete_time:
            return COMPLETE, READY
        elif topic_progress:
            return IN_PROGRESS, BLOCKED
        elif next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    elif isinstance(content_item, Form):
        form_progress = (
            FormProgress.objects.filter(user=user, form=content_item)
            .order_by("-start_time")
            .first()
        )

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
                child, user, temp_next_status
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

    elif isinstance(content_item, Course):
        # For courses, check if all direct children are complete
        # TODO: implement proper recursive course completion checking
        if next_status == READY:
            return READY, BLOCKED
        else:
            return BLOCKED, BLOCKED

    return BLOCKED, BLOCKED


def get_is_registered(user, course):
    # Check if user is registered for the course
    is_registered = False
    if user.is_authenticated:
        try:
            student = Student.objects.get(user=user)
            registered_courses = student.get_course_registrations()
            is_registered = course in registered_courses
        except Student.DoesNotExist:
            is_registered = False
    return is_registered


def get_course_index(user, course):
    """
    Generate an index of course children with their status and metadata.

    Returns a list of dictionaries with title, status, url, type, deadlines, and optionally children.
    """
    is_registered = get_is_registered(user, course)

    # Look up student and deadlines
    student = _get_student(user)
    deadlines_map: dict = {}
    if student:
        deadlines_map = get_course_deadlines(student, course)

    children = []
    next_status = READY  # First item starts as READY
    global_index = 0  # Track flattened index for nested items

    for child in course.children():
        child_dict, next_status, items_added = create_child_dict_with_flattened_index(
            child, user, course, global_index, next_status, is_registered,
            deadlines_map=deadlines_map, student=student,
        )
        children.append(child_dict)
        global_index += items_added

    return children


def _get_deadlines_for_item(
    content_item, deadlines_map: dict,
) -> list[dict]:
    """Get deadline display dicts for a content item from the pre-fetched deadlines map."""
    if not deadlines_map:
        return []

    from django.contrib.contenttypes.models import ContentType as DjangoContentType

    ct = DjangoContentType.objects.get_for_model(content_item)
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

    hard_deadlines = [d for d in deadlines if d["is_hard_deadline"] and d["is_expired"]]
    if not hard_deadlines:
        return

    # Check if ALL hard deadlines are expired (most permissive governs)
    all_hard = [d for d in deadlines if d["is_hard_deadline"]]
    most_permissive = max(all_hard, key=lambda d: d["deadline"])
    if most_permissive["is_expired"]:
        child_dict["status"] = BLOCKED
        child_dict["url"] = None


def create_child_dict_with_flattened_index(
    content_item, user, course, start_index, next_status, is_registered,
    deadlines_map: dict | None = None, student: Student | None = None,
):
    """
    Create a child dict with proper flattened indices for nested items.

    Returns tuple of (child_dict, updated_next_status, number_of_items_added)
    """
    if deadlines_map is None:
        deadlines_map = {}

    items_added = 1  # This item itself

    # Handle CoursePart specially - don't calculate its status yet, process children first
    if isinstance(content_item, CoursePart):
        part_children = content_item.children()
        part_children_dicts = []
        part_next_status = next_status  # Use the incoming next_status for children
        nested_index = start_index + 1  # Start right after the CoursePart itself

        # Calculate status and URL for each child of the CoursePart
        for part_child in part_children:
            if is_registered:
                child_status, part_next_status = get_content_status(
                    part_child, user, part_next_status
                )
                child_url = reverse(
                    "student_interface:view_course_item",
                    kwargs={"course_slug": course.slug, "index": nested_index + 1},
                )
            else:
                child_status = BLOCKED
                child_url = ""

            part_child_deadlines = _get_deadlines_for_item(part_child, deadlines_map)
            part_child_dict = {
                "title": part_child.title,
                "type": part_child.content_type,
                "url": child_url if child_status != BLOCKED else None,
                "status": child_status,
                "deadlines": part_child_deadlines,
            }
            _apply_deadline_locking(part_child_dict, part_child_deadlines)
            part_children_dicts.append(part_child_dict)
            nested_index += 1
            items_added += 1

        # Now calculate CoursePart's own status and URL based on children
        status = BLOCKED  # Default
        url = ""

        if part_children_dicts:
            # Check for READY or IN_PROGRESS children
            ready_child = next(
                (c for c in part_children_dicts if c["status"] == READY), None
            )
            in_progress_child = next(
                (c for c in part_children_dicts if c["status"] == IN_PROGRESS), None
            )

            if in_progress_child:
                # Prioritize IN_PROGRESS
                status = IN_PROGRESS
                url = in_progress_child["url"]
            elif ready_child:
                # Then READY
                status = READY
                url = ready_child["url"]
            elif all(c["status"] == COMPLETE for c in part_children_dicts):
                # All complete
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
        }

        _apply_deadline_locking(child_dict, part_deadlines)

        # Update next_status based on the last child's processing
        next_status = part_next_status

    else:
        # Regular content item (Topic, Form, etc.)
        if is_registered:
            status, next_status = get_content_status(content_item, user, next_status)
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
        }

        _apply_deadline_locking(child_dict, item_deadlines)

    return child_dict, next_status, items_added


def form_start_page_buttons(
    form, incomplete_form_progress, completed_form_progress, is_last_item
):
    """
    Determine which buttons to show on the form start page.

    Returns a list of button dicts with 'text' and 'action' keys.

    Args:
        form: Form instance
        incomplete_form_progress: FormProgress instance or None
        completed_form_progress: QuerySet of completed FormProgress objects
        is_last_item: Boolean indicating if this is the last item in the course
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


def _get_student(user) -> Student | None:
    """Get the Student instance for a user, or None if anonymous or no student."""
    if not user.is_authenticated:
        return None
    try:
        return Student.objects.get(user=user)
    except Student.DoesNotExist:
        return None


def get_completed_courses(user) -> list[Course]:
    """Get completed courses for a user. Returns empty list for anonymous users."""
    student = _get_student(user)
    if student is None:
        return []
    return student.completed_courses()


def get_current_courses(user) -> list[Course]:
    """Get current (in-progress) courses for a user. Returns empty list for anonymous users."""
    student = _get_student(user)
    if student is None:
        return []
    return student.current_courses()


def get_recommended_courses(user) -> QuerySet[RecommendedCourse]:
    """Get recommended courses for a user. Returns empty queryset for anonymous users."""
    if not user.is_authenticated:
        return RecommendedCourse.objects.none()
    return RecommendedCourse.objects.filter(user=user).select_related("collection")
