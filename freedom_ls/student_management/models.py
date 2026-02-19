from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType as DjangoContentType
from django.core.exceptions import ValidationError
from freedom_ls.site_aware_models.models import SiteAwareModel
from django.utils.translation import gettext_lazy as _

from django.contrib.auth import get_user_model

User = get_user_model()


class Student(SiteAwareModel):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    cellphone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        if self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return self.user.email or f"Student {self.pk}"

    def get_course_registrations(self):
        """Get all active course registrations for this student."""
        registered_collections = set()

        # Get direct student registrations
        student_registrations = StudentCourseRegistration.objects.filter(
            student=self
        ).select_related("collection")

        for reg in student_registrations:
            registered_collections.add(reg.collection)

        # Get cohort-based registrations through cohort memberships
        cohort_memberships = CohortMembership.objects.filter(
            student=self
        ).select_related("cohort")

        for membership in cohort_memberships:
            cohort_registrations = CohortCourseRegistration.objects.filter(
                cohort=membership.cohort
            ).select_related("collection")

            for reg in cohort_registrations:
                registered_collections.add(reg.collection)

        return list(registered_collections)

    def completed_courses(self):
        """Get all completed courses for this student."""
        from freedom_ls.student_progress.models import CourseProgress

        # Get all registered courses
        all_registered = self.get_course_registrations()
        completed = []

        for course in all_registered:
            try:
                course_progress = CourseProgress.objects.get(
                    user=self.user, course=course
                )
                if course_progress.completed_time:
                    completed.append(course)
            except CourseProgress.DoesNotExist:
                pass

        return completed

    def current_courses(self):
        """Get all current (non-completed) courses for this student."""
        from freedom_ls.student_progress.models import (
            CourseProgress,
            TopicProgress,
            FormProgress,
        )
        from freedom_ls.student_management.utils import (
            calculate_course_progress_percentage,
        )

        # Get all registered courses
        all_registered = self.get_course_registrations()
        current = []

        # Fetch all course progress for this user in one query
        course_progress_dict = {
            cp.course_id: cp
            for cp in CourseProgress.objects.filter(
                user=self.user, course__in=all_registered
            ).select_related("course")
        }

        # Collect all topic and form IDs (including nested in CourseParts)
        topic_ids = []
        form_ids = []

        def collect_ids(children):
            """Recursively collect topic and form IDs from children."""
            for child in children:
                if child.content_type == "COURSE_PART":
                    collect_ids(child.children())
                elif child.content_type == "TOPIC":
                    topic_ids.append(child.id)
                elif child.content_type == "FORM":
                    form_ids.append(child.id)

        for course in all_registered:
            collect_ids(course.children())

        # Get completed topics and forms
        completed_topics = set(
            TopicProgress.objects.filter(
                user=self.user, topic_id__in=topic_ids, complete_time__isnull=False
            ).values_list("topic_id", flat=True)
        )

        completed_forms = set(
            FormProgress.objects.filter(
                user=self.user, form_id__in=form_ids, completed_time__isnull=False
            ).values_list("form_id", flat=True)
        )

        for course in all_registered:
            course_progress = course_progress_dict.get(course.id)

            # Only include non-completed courses
            if course_progress and course_progress.completed_time:
                continue

            # Calculate percentage complete using utility function
            percentage = calculate_course_progress_percentage(
                course, completed_topics, completed_forms
            )

            # Attach percentage to course object as an attribute
            course.progress_percentage = percentage
            current.append(course)

        return current


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
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE)

    def __str__(self):
        return ""


class StudentCourseRegistration(SiteAwareModel):
    """Individual student registration for a course."""

    collection = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="student_registrations",
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="course_registrations"
    )
    is_active = models.BooleanField(default=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site_id", "collection", "student"],
                name="unique_student_course_registration",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.collection}"


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
        StudentCourseRegistration,
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
        return f"{reg.student} - {reg.collection} - {item_label}"


class StudentCohortDeadlineOverride(SiteAwareModel):
    """Override deadline for a specific student within a cohort."""

    cohort_course_registration = models.ForeignKey(
        CohortCourseRegistration,
        on_delete=models.CASCADE,
        related_name="deadline_overrides",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="cohort_deadline_overrides",
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
                fields=[
                    "cohort_course_registration",
                    "student",
                    "content_type",
                    "object_id",
                ],
                name="unique_student_cohort_override_per_item",
                condition=models.Q(content_type__isnull=False, object_id__isnull=False),
            ),
        ]

    def clean(self) -> None:
        super().clean()
        # Validate student is a member of the cohort
        if not CohortMembership.objects.filter(
            student=self.student,
            cohort=self.cohort_course_registration.cohort,
        ).exists():
            raise ValidationError(
                "Student is not a member of the cohort for this registration."
            )

        # Validate uniqueness for course-level overrides (null content)
        if self.content_type is None and self.object_id is None:
            existing = StudentCohortDeadlineOverride.objects.filter(
                cohort_course_registration=self.cohort_course_registration,
                student=self.student,
                content_type__isnull=True,
                object_id__isnull=True,
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    "A course-level override already exists for this student and cohort registration."
                )

    def __str__(self) -> str:
        reg = self.cohort_course_registration
        item_label = str(self.content_item) if self.content_item else "Whole course"
        return f"{self.student} - {reg.cohort} - {reg.collection} - {item_label}"


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
