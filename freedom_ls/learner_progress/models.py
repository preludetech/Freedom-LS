from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from freedom_ls.content_engine.models import ContentCollectionItem, Course, Topic
from freedom_ls.form_engine.models import Form, FormProgress
from freedom_ls.learner_management.models import (
    CohortCourseRegistration,
    CohortMembership,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.site_aware_models.models import SiteAwareModel


class CourseItemProgress(SiteAwareModel):
    # Subclasses must define these class attributes. signals.py reads them off
    # the instance to find the completion field and the item it belongs to.
    completion_field_name: str
    content_item_field_name: str
    course_progress: models.Model  # Declared here for mypy; actual FK on subclasses

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
    """One learner's progress through one placement of a topic.

    `start_time` is this row's own: a topic progress row is still created the
    moment the learner opens the topic, so "began" is its creation -- unlike a
    `CourseProgress`, which exists from registration onward.
    """

    completion_field_name = "complete_time"
    content_item_field_name = "topic"

    course_progress = models.ForeignKey(
        "CourseProgress", on_delete=models.CASCADE, related_name="topic_progress"
    )
    #: The collection item placing the topic, not the topic itself: one topic
    #: may be placed twice in one course, and each placement is its own item.
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="topic_progress",
    )
    #: What was completed. Kept alongside the collection item so a completion
    #: outlives the placement being removed.
    topic = models.ForeignKey(
        Topic, on_delete=models.PROTECT, related_name="progress_records"
    )
    start_time = models.DateTimeField(auto_now_add=True)
    last_accessed_time = models.DateTimeField(auto_now=True)
    complete_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "topic progress record"
        verbose_name_plural = "topic progress records"
        constraints = [
            models.UniqueConstraint(
                fields=["course_progress", "collection_item"],
                name="one_topic_progress_per_placement_per_record",
            )
        ]
        indexes = [models.Index(fields=["course_progress", "complete_time"])]

    def __str__(self):
        return f"{self.course_progress.learner} - {self.topic.title}"


class CourseProgress(SiteAwareModel):
    """One learner's pass through one course, granted by one registration."""

    learner = models.ForeignKey(
        Learner, on_delete=models.PROTECT, related_name="course_progress_records"
    )
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="progress_records"
    )

    # Exactly one is set, and PROTECT keeps it that way: a registration that
    # granted a record cannot be deleted. Bound to the registration, never to
    # CohortMembership -- membership churn is a bad lifecycle signal.
    learner_registration = models.ForeignKey(
        LearnerCourseRegistration,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="course_progress_records",
    )
    cohort_registration = models.ForeignKey(
        CohortCourseRegistration,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="course_progress_records",
    )

    # The registration minted this row, so created_at is the registration date
    # and started_at is the first content access. Nothing may read one for the
    # other. last_accessed_time is written by the player, not by auto_now: a
    # background percentage recalculation must not look like a visit.
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    last_accessed_time = models.DateTimeField(null=True, blank=True)
    completed_time = models.DateTimeField(blank=True, null=True)
    progress_percentage = models.IntegerField(default=0, db_index=True)

    #: The resume pointer: the collection item the learner last visited, not
    #: the child it resolves to, so resume still names a position once a topic
    #: can be placed twice in one course.
    last_accessed_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        verbose_name = "course progress record"
        verbose_name_plural = "course progress records"
        constraints = [
            # One record per learner per registration. NULLs are distinct in a
            # PostgreSQL unique index, so a cohort-granted record (which has a
            # null learner_registration) never collides in the first index, and
            # vice versa.
            models.UniqueConstraint(
                fields=["learner_registration", "learner"],
                name="one_course_progress_per_learner_registration",
            ),
            models.UniqueConstraint(
                fields=["cohort_registration", "learner"],
                name="one_course_progress_per_cohort_registration",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        learner_registration__isnull=False,
                        cohort_registration__isnull=True,
                    )
                    | models.Q(
                        learner_registration__isnull=True,
                        cohort_registration__isnull=False,
                    )
                ),
                name="course_progress_has_exactly_one_grant",
            ),
        ]
        indexes = [models.Index(fields=["learner", "course"])]

    def clean(self) -> None:
        super().clean()
        try:
            learner = self.learner
            course = self.course
        except ObjectDoesNotExist:
            # An unset FK means the form already holds a field-level error for
            # it; returning lets that surface instead of a crash out of clean().
            return

        if learner.site_id != course.site_id:
            raise ValidationError("Learner and course must belong to the same site.")

        learner_registration = self.learner_registration
        if learner_registration is not None:
            if learner_registration.collection_id != self.course_id:
                raise ValidationError(
                    "The learner registration must be for this course."
                )
            if learner_registration.learner_id != self.learner_id:
                raise ValidationError(
                    "The learner registration must belong to this learner."
                )

        cohort_registration = self.cohort_registration
        if cohort_registration is not None:
            if cohort_registration.collection_id != self.course_id:
                raise ValidationError(
                    "The cohort registration must be for this course."
                )
            # Organisation grain, always: CohortMembership.clean() already
            # forbids a cross-organisation membership, so this half of the
            # pairing survives the learner being removed from the cohort.
            if learner.organisation_id != cohort_registration.cohort.organisation_id:
                raise ValidationError(
                    "Learner and cohort must belong to the same organisation."
                )
            # Membership, only while the record is new. A learner removed from
            # the cohort keeps this record, and an unconditional check would
            # make it permanently unsaveable.
            if (
                self._state.adding
                and not CohortMembership.objects.filter(
                    cohort_id=cohort_registration.cohort_id,
                    learner_id=self.learner_id,
                ).exists()
            ):
                raise ValidationError(
                    "The learner is not a member of the registered cohort."
                )

    def __str__(self):
        return f"{self.learner} - {self.course.title}"


class CourseFormAttempt(SiteAwareModel):
    """One form attempt, sat at one placement, inside one course progress record.

    The attempt itself -- its answers, its score, when it was completed -- is a
    `form_engine.FormProgress`, which knows nothing about courses so that a form
    can also be sat outside one. This row is the course's side of that attempt,
    and its absence is what marks an attempt as having been sat somewhere else.

    No uniqueness constraint on the placement: many attempts per
    (record, placement), one row each, as retaking a quiz has always allowed.
    """

    course_progress = models.ForeignKey(
        CourseProgress, on_delete=models.CASCADE, related_name="form_attempts"
    )
    #: The collection item placing the form, not the form itself: the same form
    #: may be placed twice in one course, and each placement is its own item.
    #: Nullable so removing a placement does not erase the sitting -- the
    #: attempt still names its form.
    collection_item = models.ForeignKey(
        ContentCollectionItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="form_attempts",
    )
    form_progress = models.OneToOneField(
        FormProgress, on_delete=models.CASCADE, related_name="course_attempt"
    )

    class Meta:
        verbose_name = "course form attempt"
        verbose_name_plural = "course form attempts"
        indexes = [models.Index(fields=["course_progress", "collection_item"])]

    def __str__(self):
        return f"{self.course_progress.learner} - {self.form_progress.form.title}"
