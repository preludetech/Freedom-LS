from django.db import models

from freedom_ls.content_engine.models import ContentCollectionItem, Course


class DeadlineKind(models.TextChoices):
    FIXED = "fixed", "Fixed date"
    RELATIVE = "relative", "Days after registration"
    NONE = "none", "No deadline"


def course_viewable_collection_items(course: Course) -> list[ContentCollectionItem]:
    """The rows a deadline can attach to: the course's own and its parts', in order."""
    return course.viewable_collection_items()
