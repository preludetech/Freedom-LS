from __future__ import annotations

from datetime import date, time
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.learner_management.models import CohortCourseRegistration
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

if TYPE_CHECKING:
    from freedom_ls.deadlines.resolver import DeadlineValue


class DeadlineKind(models.TextChoices):
    FIXED = "fixed", "Fixed date"
    RELATIVE = "relative", "Days after registration"
    NONE = "none", "No deadline"


def _validate_deadline_override(
    kind: str,
    due_date: date | None,
    due_time: time | None,
    due_days_after_registration: int | None,
    collection_item: ContentCollectionItem | None,
    course: Course,
) -> None:
    """The shape rules every override row obeys, raised as one ValidationError."""
    errors: dict[str, str] = {}
    if kind == DeadlineKind.FIXED:
        if due_date is None:
            errors["due_date"] = "A fixed deadline needs a date."
        if due_days_after_registration is not None:
            errors["due_days_after_registration"] = "A fixed deadline takes no days."
    if kind == DeadlineKind.RELATIVE:
        if due_days_after_registration is None:
            errors["due_days_after_registration"] = (
                "A relative deadline needs a number of days."
            )
        if due_date is not None:
            errors["due_date"] = "A relative deadline takes no date."
    if kind == DeadlineKind.NONE and (
        due_date or due_time or due_days_after_registration is not None
    ):
        errors["kind"] = "No deadline takes no date, time or days."
    if collection_item is None:
        if kind == DeadlineKind.FIXED:
            errors["kind"] = (
                "The course time limit is counted in days after registration."
            )
        if due_time is not None:
            errors["due_time"] = "The course time limit ends at the end of its day."
    elif collection_item not in course.viewable_collection_items():
        errors["collection_item"] = "Pick an item of this course."
    if errors:
        raise ValidationError(errors)


class CohortDeadlineOverride(SiteAwareModel, TimestampedModel):
    """A deadline set for every learner registered for a course through a cohort."""

    cohort_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    kind = models.CharField(max_length=8, choices=DeadlineKind.choices)
    due_date = models.DateField(
        null=True, blank=True, help_text="Read in the site's time zone."
    )
    due_time = models.TimeField(null=True, blank=True)
    due_days_after_registration = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="days after registration"
    )
    replaced_value = models.CharField(max_length=64, blank=True)
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cohort_registration", "collection_item"],
                condition=Q(collection_item__isnull=False),
                name="unique_cohort_override_per_item",
            ),
            models.UniqueConstraint(
                fields=["cohort_registration"],
                condition=Q(collection_item__isnull=True),
                name="unique_cohort_time_limit_override",
            ),
        ]
        verbose_name = "deadline override"

    @property
    def course(self) -> Course | None:
        # The parent is unset while the admin add page is still being validated.
        return self.cohort_registration.course if self.cohort_registration_id else None

    def value(self) -> DeadlineValue:
        from freedom_ls.deadlines.resolver import DeadlineValue

        return DeadlineValue(
            DeadlineKind(self.kind),
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
        )

    def clean(self) -> None:
        course = self.course
        if course is None:
            return
        _validate_deadline_override(
            self.kind,
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
            self.collection_item,
            course,
        )


class LearnerDeadlineOverride(SiteAwareModel, TimestampedModel):
    """A deadline set for one learner's progress on a course. It beats a cohort override and
    the content default."""

    course_progress = models.ForeignKey(
        CourseProgress,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    kind = models.CharField(max_length=8, choices=DeadlineKind.choices)
    due_date = models.DateField(
        null=True, blank=True, help_text="Read in the site's time zone."
    )
    due_time = models.TimeField(null=True, blank=True)
    due_days_after_registration = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="days after registration"
    )
    replaced_value = models.CharField(max_length=64, blank=True)
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course_progress", "collection_item"],
                condition=Q(collection_item__isnull=False),
                name="unique_learner_override_per_item",
            ),
            models.UniqueConstraint(
                fields=["course_progress"],
                condition=Q(collection_item__isnull=True),
                name="unique_learner_time_limit_override",
            ),
        ]
        verbose_name = "deadline override"

    @property
    def course(self) -> Course | None:
        # The parent is unset while the admin add page is still being validated.
        return self.course_progress.course if self.course_progress_id else None

    def value(self) -> DeadlineValue:
        from freedom_ls.deadlines.resolver import DeadlineValue

        return DeadlineValue(
            DeadlineKind(self.kind),
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
        )

    def clean(self) -> None:
        course = self.course
        if course is None:
            return
        _validate_deadline_override(
            self.kind,
            self.due_date,
            self.due_time,
            self.due_days_after_registration,
            self.collection_item,
            course,
        )
