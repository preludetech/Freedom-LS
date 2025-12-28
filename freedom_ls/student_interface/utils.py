from django.urls import reverse
from freedom_ls.content_engine.models import Topic, Form, Course, FormStrategy
from freedom_ls.student_progress.models import FormProgress, TopicProgress
from freedom_ls.student_management.models import Student


def get_is_registered(request, course):
    # Check if user is registered for the course
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
    BLOCKED = "BLOCKED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"

    is_registered = get_is_registered(request, course)

    # Get the children of this course
    children = [
        # {title, status, url}
    ]

    if is_registered:
        next_status = READY  # First item starts as READY
        for index, child in enumerate(course.children()):
            # create a list of children dicts
            # status is either blocked, ready, in progress or complete
            # users need to complete things in order, an item is blocked if the previous item has not been completed yet

            status = None
            url = reverse(
                "student_interface:view_course_item",
                kwargs={"course_slug": course.slug, "index": index + 1},
            )
            title = None

            if isinstance(child, Topic):
                title = child.title
                child_type = "topic"

                # Check progress
                topic_progress = TopicProgress.objects.filter(
                    user=request.user, topic=child
                ).first()

                if topic_progress and topic_progress.complete_time:
                    status = COMPLETE
                elif topic_progress:
                    status = IN_PROGRESS
                elif next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            elif isinstance(child, Form):
                title = child.title
                child_type = "form"

                # Check progress
                form_progress = (
                    FormProgress.objects.filter(user=request.user, form=child)
                    .order_by("-start_time")
                    .first()
                )

                if form_progress and form_progress.completed_time:
                    if form_progress.form.strategy == FormStrategy.QUIZ:
                        if form_progress.passed():
                            status = COMPLETE
                        else:
                            status = FAILED
                    else:
                        status = COMPLETE
                elif form_progress:
                    status = IN_PROGRESS
                elif next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            elif isinstance(child, Course):
                NotImplemented
                title = child.title
                child_type = "course"
                # url = reverse(
                #     "student_interface:course_home",
                #     kwargs={"course_slug": child.slug},
                # )
                url = "todo"

                # For courses, check if all direct children are complete
                # TODO: implement proper recursive course completion checking
                if next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            children.append(
                {
                    "title": title,
                    "status": status,
                    "url": url if status != BLOCKED else None,
                    "type": child_type,
                }
            )

            # Update next_status for the next iteration
            if status == COMPLETE:
                next_status = READY
            else:
                next_status = BLOCKED

    else:
        children = []
        for child in course.children():
            if isinstance(child, Topic):
                child_type = "topic"
            elif isinstance(child, Form):
                child_type = "form"
            elif isinstance(child, Course):
                child_type = "course"
            else:
                child_type = "unknown"

            children.append(
                {
                    "title": child.title,
                    "status": BLOCKED,
                    "url": "",
                    "type": child_type,
                }
            )
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
