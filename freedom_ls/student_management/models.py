from django.db import models
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

        # Prefetch all topic and form progress for efficiency
        topic_ids = []
        form_ids = []
        for course in all_registered:
            for child in course.children():
                if child.content_type == "TOPIC":
                    topic_ids.append(child.id)
                elif child.content_type == "FORM":
                    form_ids.append(child.id)

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

            # Calculate percentage complete
            children = course.children()
            if children:
                total_items = len(children)
                completed_items = 0

                for child in children:
                    if child.content_type == "TOPIC" and child.id in completed_topics:
                        completed_items += 1
                    elif child.content_type == "FORM" and child.id in completed_forms:
                        completed_items += 1

                percentage = round((completed_items / total_items) * 100)
            else:
                percentage = 0

            # Attach percentage to course object as an attribute
            course.progress_percentage = percentage
            # @claude: refactor this. Make a separate function that calculates the course progress percentage. Write some basic tests to make sure it basically works.
            # @claude. Then upgrade it so it looks at items inside CourseParts
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
