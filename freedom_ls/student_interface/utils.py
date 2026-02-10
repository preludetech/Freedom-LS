from django.urls import reverse
from freedom_ls.content_engine.models import (
    Topic,
    Form,
    Course,
    CoursePart,
    FormStrategy,
)
from freedom_ls.student_progress.models import FormProgress, TopicProgress
from freedom_ls.student_management.models import Student

# Status constants
BLOCKED = "BLOCKED"
READY = "READY"
IN_PROGRESS = "IN_PROGRESS"
COMPLETE = "COMPLETE"
FAILED = "FAILED"


def get_content_status(content_item, request, next_status):
    """
    Get the status for a content item based on user progress.

    Returns tuple of (status, updated_next_status)
    """
    # @claude: dont require a request argument. Rather just take a user
    if isinstance(content_item, Topic):
        topic_progress = TopicProgress.objects.filter(
            user=request.user, topic=content_item
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
            FormProgress.objects.filter(user=request.user, form=content_item)
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
        # For course parts, check if all direct children are complete
        # @claude:  implement proper recursive course part completion checking
        if next_status == READY:
            return READY, BLOCKED
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


def create_child_dict(content_item, request, course, index, next_status, is_registered):
    """
    Create a standardized dictionary for a content item.

    Returns tuple of (child_dict, updated_next_status)
    """
    # @claude: dont require a request argument. Rather just take a user

    child_type = content_item.content_type

    if is_registered:
        status, next_status = get_content_status(content_item, request, next_status)
        url = reverse(
            "student_interface:view_course_item",
            kwargs={"course_slug": course.slug, "index": index + 1},
        )
    else:
        status = BLOCKED
        url = ""

    child_dict = {
        "title": content_item.title,
        "status": status,
        "url": url if status != BLOCKED else None,
        "type": child_type,
    }

    # Add children for CoursePart
    if isinstance(content_item, CoursePart):
        part_children = content_item.children()
        child_dict["children"] = [
            {
                "title": part_child.title,
                "type": part_child.content_type,
                # @claude: add the url here. Follow TDD
                # @claude: add the status here. Follow TDD
            }
            for part_child in part_children
        ]
        # @claude: course part url and status should be calculated as follows:
        # if there is a READY child:
        # url = child url. status=READY
        # if there is an IN PROGRESS child:
        # url = child url. status=IN PROGRESS
        # if all children are COMPLETE
        # status = COMPLETE. url = first child url
        # if should be blocked:
        # url = None

    return child_dict, next_status


def get_is_registered(request, course):
    # Check if user is registered for the course
    # @claude: dont require a request argument. Rather just take a user

    is_registered = False
    if request.user.is_authenticated:
        try:
            student = Student.objects.get(user=request.user)
            registered_courses = student.get_course_registrations()
            is_registered = course in registered_courses
        except Student.DoesNotExist:
            is_registered = False
    return is_registered


def get_course_index(request, course):
    """
    Generate an index of course children with their status and metadata.

    Returns a list of dictionaries with title, status, url, type, and optionally children.
    """
    # @claude: dont require a request argument. Rather just take a user

    is_registered = get_is_registered(request, course)
    children = []
    next_status = READY  # First item starts as READY

    for index, child in enumerate(course.children()):
        child_dict, next_status = create_child_dict(
            child, request, course, index, next_status, is_registered
        )
        children.append(child_dict)

    return children


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
