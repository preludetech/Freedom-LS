from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone
from content_engine.models import Topic, Form, ContentCollection
from student_progress.models import FormProgress, TopicProgress, QuestionAnswer
from student_management.models import Student, StudentCourseRegistration


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
                kwargs={"collection_slug": course.slug, "index": index + 1},
            )
            title = None

            if isinstance(child, Topic):
                title = child.title

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

                # Check progress
                form_progress = (
                    FormProgress.objects.filter(user=request.user, form=child)
                    .order_by("-start_time")
                    .first()
                )

                if form_progress and form_progress.completed_time:
                    status = COMPLETE
                elif form_progress:
                    status = IN_PROGRESS
                elif next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            elif isinstance(child, ContentCollection):
                NotImplemented
                title = child.title
                # url = reverse(
                #     "student_interface:course_home",
                #     kwargs={"collection_slug": child.slug},
                # )
                url = "todo"

                # For collections, check if all direct children are complete
                # TODO: implement proper recursive collection completion checking
                if next_status == READY:
                    status = READY
                else:
                    status = BLOCKED

            children.append(
                {
                    "title": title,
                    "status": status,
                    "url": url if status != BLOCKED else None,
                }
            )

            # Update next_status for the next iteration
            if status == COMPLETE:
                next_status = READY
            else:
                next_status = BLOCKED

    else:
        children = [
            {"title": child.title, "status": BLOCKED, "url": ""}
            for child in course.children()
        ]
    return children
