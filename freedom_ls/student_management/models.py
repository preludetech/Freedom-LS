from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from freedom_ls.site_aware_models.models import SiteAwareModel

User = get_user_model()


class Cohort(SiteAwareModel):
    name = models.CharField(_("name"), max_length=150)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "name"], name="unique_cohort_name_per_site"
            )
        ]

    def __str__(self):
        return self.name


class CohortMembership(SiteAwareModel):
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "cohort"],
                name="unique_user_cohort_membership",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.cohort}"


class UserCourseRegistration(SiteAwareModel):
    """Individual user registration for a course."""

    collection = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="user_registrations",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "collection", "user"],
                name="unique_user_course_registration",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            from freedom_ls.webhooks.events import fire_webhook_event

            fire_webhook_event(
                "course.registered",
                {
                    "user_id": self.user_id,
                    "user_email": self.user.email,
                    "course_id": str(self.collection_id),
                    "course_title": self.collection.title,
                    "registered_at": self.registered_at.isoformat(),
                },
            )

    def __str__(self):
        return f"{self.user} - {self.collection}"


class CohortCourseRegistration(SiteAwareModel):
    """Cohort-wide registration for a course."""

    collection = models.ForeignKey(
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
                fields=["site_id", "collection", "cohort"],
                name="unique_cohort_course_registration",
            )
        ]

    def __str__(self):
        return f"{self.cohort} - {self.collection}"


class CohortDeadline(SiteAwareModel):
    """Deadline applied to all students in a cohort for a specific course registration."""

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
        return f"{reg.cohort} - {reg.collection} - {item_label}"


class StudentDeadline(SiteAwareModel):
    """Deadline for a student registered individually for a course."""

    student_course_registration = models.ForeignKey(
        UserCourseRegistration,
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
                fields=["student_course_registration", "content_type", "object_id"],
                name="unique_student_deadline_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.content_type is None and self.object_id is None:
            existing = StudentDeadline.objects.filter(
                student_course_registration=self.student_course_registration,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level deadline already exists for this student registration."
                )

    def __str__(self) -> str:
        reg = self.student_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{reg.user} - {reg.collection} - {item_label}"


class UserCohortDeadlineOverride(SiteAwareModel):
    """Override deadline for a specific user within a cohort."""

    cohort_course_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
                    "user",
                    "content_type",
                    "object_id",
                ],
                name="unique_user_cohort_override_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        # Validate user is a member of the cohort
        if not CohortMembership.objects.filter(
            user=self.user,
            cohort=self.cohort_course_registration.cohort,
        ).exists():
            raise ValidationError(
                "User is not a member of the cohort for this registration."
            )

        # Validate uniqueness for course-level overrides (null content)
        if self.content_type is None and self.object_id is None:
            existing = UserCohortDeadlineOverride.objects.filter(
                cohort_course_registration=self.cohort_course_registration,
                user=self.user,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level override already exists for this user and cohort registration."
                )

    def __str__(self) -> str:
        reg = self.cohort_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{self.user} - {reg.cohort} - {reg.collection} - {item_label}"


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
    collection = models.ForeignKey(
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
        return f"Course recommendation for {self.user.email}: {self.collection.title}"
