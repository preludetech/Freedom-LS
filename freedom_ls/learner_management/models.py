from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import SiteAwareModel, TimestampedModel

User = get_user_model()


def _relations_are_set(instance: models.Model, *field_names: str) -> bool:
    """Whether every named foreign key on ``instance`` resolves.

    An unset one means the form already holds a field-level error for it -- an
    invalid choice in an admin inline, say. Callers return early on False so
    that error surfaces instead of a RelatedObjectDoesNotExist crash out of
    clean().
    """
    try:
        for field_name in field_names:
            getattr(instance, field_name)
    except ObjectDoesNotExist:
        return False
    return True


class Cohort(SiteAwareModel, TimestampedModel):
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation",
        on_delete=models.PROTECT,
    )
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "organisation", "name"],
                name="unique_cohort_name_per_site",
            )
        ]

    def __str__(self):
        return self.name


class Learner(SiteAwareModel):
    """A user's association with an organisation for enrolment purposes.

    A user may hold a Learner row in more than one organisation. Enrolment
    records (CohortMembership, LearnerCourseRegistration) hang off Learner
    rather than User, so an enrolment with no organisation association
    cannot be represented.

    Self-service registration on the default organisation reactivates a
    removed learner rather than refusing it: registering again is treated as
    a live signal of re-association, so ensure_learner overwrites
    is_active=False instead of erroring on it.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        "freedom_ls_organisations.Organisation", on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organisation"], name="unique_learner_per_organisation"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.organisation}"


class CohortMembership(SiteAwareModel, TimestampedModel):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE)
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "cohort"],
                name="unique_learner_cohort_membership",
            )
        ]

    def clean(self) -> None:
        super().clean()
        if not _relations_are_set(self, "learner", "cohort"):
            return
        if self.learner.organisation_id != self.cohort.organisation_id:
            raise ValidationError(
                "Learner and cohort must belong to the same organisation."
            )

    def __str__(self):
        return f"{self.learner} - {self.cohort}"


class LearnerCourseRegistration(SiteAwareModel):
    """Individual learner registration for a course."""

    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="learner_registrations",
    )
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "learner", "course"],
                name="unique_learner_course_registration",
            )
        ]

    def __str__(self):
        return f"{self.learner} - {self.course}"


class CohortCourseRegistration(SiteAwareModel):
    """Cohort-wide registration for a course."""

    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="cohort_registrations",
    )
    cohort = models.ForeignKey(
        Cohort, on_delete=models.CASCADE, related_name="course_registrations"
    )
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "course", "cohort"],
                name="unique_cohort_course_registration",
            )
        ]

    def __str__(self):
        return f"{self.cohort} - {self.course}"


class CohortDeadline(SiteAwareModel, TimestampedModel):
    """Deadline applied to all learners in a cohort for a specific course registration."""

    cohort_course_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )
    content_type = models.ForeignKey(
        DjangoContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_item = GenericForeignKey("content_type", "object_id")
    deadline = models.DateTimeField()
    is_hard_deadline = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["cohort_course_registration", "content_type", "object_id"],
                name="unique_cohort_deadline_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.content_type is None and self.object_id is None:
            existing = CohortDeadline.objects.filter(
                cohort_course_registration=self.cohort_course_registration,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level deadline already exists for this cohort registration."
                )

    def __str__(self) -> str:
        reg = self.cohort_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{reg.cohort} - {reg.course} - {item_label}"


class LearnerDeadline(SiteAwareModel, TimestampedModel):
    """Deadline for a learner registered individually for a course."""

    learner_course_registration = models.ForeignKey(
        LearnerCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )
    content_type = models.ForeignKey(
        DjangoContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_item = GenericForeignKey("content_type", "object_id")
    deadline = models.DateTimeField()
    is_hard_deadline = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner_course_registration", "content_type", "object_id"],
                name="unique_learner_deadline_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.content_type is None and self.object_id is None:
            existing = LearnerDeadline.objects.filter(
                learner_course_registration=self.learner_course_registration,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level deadline already exists for this learner registration."
                )

    def __str__(self) -> str:
        reg = self.learner_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{reg.learner.user} - {reg.course} - {item_label}"


class LearnerCohortDeadlineOverride(SiteAwareModel, TimestampedModel):
    """Override deadline for a specific learner within a cohort."""

    cohort_course_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    learner = models.ForeignKey(Learner, on_delete=models.CASCADE)
    content_type = models.ForeignKey(
        DjangoContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_item = GenericForeignKey("content_type", "object_id")
    deadline = models.DateTimeField()
    is_hard_deadline = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "cohort_course_registration",
                    "learner",
                    "content_type",
                    "object_id",
                ],
                name="unique_learner_cohort_override_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if not _relations_are_set(self, "learner", "cohort_course_registration"):
            return

        # Validate the learner is a member of the cohort
        if not CohortMembership.objects.filter(
            learner=self.learner,
            cohort=self.cohort_course_registration.cohort,
        ).exists():
            raise ValidationError(
                "Learner is not a member of the cohort for this registration."
            )

        # Validate uniqueness for course-level overrides (null content)
        if self.content_type is None and self.object_id is None:
            existing = LearnerCohortDeadlineOverride.objects.filter(
                cohort_course_registration=self.cohort_course_registration,
                learner=self.learner,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level override already exists for this learner and cohort registration."
                )

    def __str__(self) -> str:
        reg = self.cohort_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{self.learner} - {reg.cohort} - {reg.course} - {item_label}"


class RecommendedCourse(SiteAwareModel):
    """
    Course recommendations for users.
    Created when a parent fills out a form.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="recommended_courses",
    )
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    # form_progress = models.ForeignKey(
    #     FormProgress, on_delete=models.CASCADE, null=True, blank=True
    # )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Recommended courses"

    def __str__(self):
        return f"Course recommendation for {self.user.email}: {self.course.title}"
