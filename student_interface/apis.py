from ninja import Router, Schema
from ninja.errors import HttpError
from typing import List, Optional
from django.shortcuts import get_object_or_404

from student_management.models import Student
from content_engine.models import ContentCollection, Topic, Form
from student_interface.models import FormProgress, TopicProgress

from allauth.headless.contrib.ninja.security import x_session_token_auth


router = Router()


class CourseRegistrationSchema(Schema):
    """Schema for a course registration."""

    id: str
    title: str
    slug: str
    subtitle: Optional[str] = None


@router.get(
    "/courses", response=List[CourseRegistrationSchema], auth=[x_session_token_auth]
)
def get_student_courses(request):
    """
    Get all courses that the currently logged in student is registered for.
    The student logged in using the allauth login api.
    """

    # Get the authenticated user
    user = request.auth

    # Check if user is authenticated
    if not user.is_authenticated:
        raise HttpError(401, "Authentication required")

    # Get the student record for this user
    try:
        student = Student.objects.get(user=user)
    except Student.DoesNotExist:
        raise HttpError(403, "No student record found for this user")

    # Get all registered collections
    collections = student.get_course_registrations()

    # Convert to schema format
    return [
        {
            "id": str(collection.id),
            "title": collection.title,
            "slug": collection.slug,
            "subtitle": collection.subtitle,
        }
        for collection in collections
    ]


class CourseItemSchema(Schema):
    """Schema for a single item in a course."""
    title: str
    slug: str
    content_type: str  # "topic", "form", or "collection"
    status: str  # "BLOCKED", "READY", "IN_PROGRESS", or "COMPLETE"


@router.get("/courses/{slug}/index", response=List[CourseItemSchema], auth=[x_session_token_auth])
def get_course_index(request, slug: str):
    """
    Get an ordered list of all the course contents.
    Returns the same information as views.course_home, but as a data structure.
    """
    # Get the authenticated user
    user = request.auth

    # Check if user is authenticated
    if not user.is_authenticated:
        raise HttpError(401, "Authentication required")

    # Get the collection
    collection = get_object_or_404(ContentCollection, slug=slug)

    # TODO: Check that the student is registered for the course

    BLOCKED = "BLOCKED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"

    items = []
    next_status = READY  # First item starts as READY

    for child in collection.children():
        status = None
        title = None
        child_slug = None
        content_type = None

        if isinstance(child, Topic):
            title = child.title
            child_slug = child.slug
            content_type = "topic"

            # Check progress
            topic_progress = TopicProgress.objects.filter(
                user=user, topic=child
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
            child_slug = child.slug
            content_type = "form"

            # Check progress
            form_progress = (
                FormProgress.objects.filter(user=user, form=child)
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
            title = child.title
            child_slug = child.slug
            content_type = "collection"

            # For collections, check if all direct children are complete
            # TODO: implement proper recursive collection completion checking
            if next_status == READY:
                status = READY
            else:
                status = BLOCKED

        items.append({
            "title": title,
            "slug": child_slug,
            "content_type": content_type,
            "status": status,
        })

        # Update next_status for the next iteration
        if status == COMPLETE:
            next_status = READY
        else:
            next_status = BLOCKED

    return items