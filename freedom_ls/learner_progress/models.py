from __future__ import annotations

from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.db import models

from freedom_ls.content_engine.models import Course, Topic
from freedom_ls.form_engine.models import Form
from freedom_ls.site_aware_models.models import SiteAwareModel

User = get_user_model()


class CourseItemProgress(SiteAwareModel):
    # Subclasses must define these class attributes. signals.py reads them off
    # the instance to find the completion field and the item it belongs to.
    completion_field_name: str
    content_item_field_name: str
    user: models.Model  # Declared here for mypy; actual FK field on subclasses

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_completion_value: datetime | None = getattr(
            self, self.completion_field_name, None
        )

    def newly_completed_item(self) -> Topic | Form | None:
        """The content item this instance has just been completed for, if any.

        None for a row that was already complete when it was loaded or built, and
        None once the completion has been recorded: completing an item is a
        transition, and a row that arrives complete never made one.

        # @claude calculate _original_completion_value here instead of during __init__. Remove the __init__ function
        """
        current_value: datetime | None = getattr(self, self.completion_field_name)
        if current_value is None or self._original_completion_value is not None:
            return None
        item: Topic | Form = getattr(self, self.content_item_field_name)
        return item

    def mark_completion_recorded(self) -> None:
        """Stop `newly_completed_item()` reporting a transition already acted on.

        `complete()` saves three times over one completion; without this the
        recalculation would run on each.
        """
        self._original_completion_value = getattr(self, self.completion_field_name)


class TopicProgress(CourseItemProgress):
    """Tracks a learner's progress through a topic."""

    completion_field_name = "complete_time"
    content_item_field_name = "topic"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="topic_progress"
    )
    topic = models.ForeignKey(
        Topic, on_delete=models.CASCADE, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    complete_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Topic progress records"
        unique_together = ["user", "topic"]

    def __str__(self):
        return f"{self.user} - {self.topic.title}"


class CourseProgress(SiteAwareModel):
    """Tracks a learner's progress through a course.

    IMPORTANT!! These are only created when a user EXPLICITY chooses to register a learner for a course.
    In some cases a learner will register themselves for a course by choosing to start the course
    In some cases an educator/staff user will register a learner for a course.

    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="course_progress"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    completed_time = models.DateTimeField(blank=True, null=True)
    progress_percentage = models.IntegerField(default=0, db_index=True)

    # The viewable item (Topic | Form) the learner last visited in this course.
    # Used as the resume target for the bare course URL. Polymorphic, so a
    # GenericForeignKey, mirroring learner_management.CohortDeadline. Nullable:
    # existing rows and freshly-registered (0-progress) learners have none and
    # resume at the first item. SET_NULL on the content-type FK so deleting a
    # content model type cannot cascade-delete progress; a dangling object_id
    # simply resolves to None and falls back to item 1.
    last_accessed_content_type = models.ForeignKey(
        DjangoContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_accessed_object_id = models.UUIDField(null=True, blank=True)
    last_accessed_item = GenericForeignKey(
        "last_accessed_content_type", "last_accessed_object_id"
    )

    class Meta:
        verbose_name_plural = "Course progress records"
        unique_together = ["user", "course"]

    def __str__(self):
        return f"{self.user} - {self.course.title}"
