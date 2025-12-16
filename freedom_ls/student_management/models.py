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
        "content_engine.Course",
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
        "content_engine.Course",
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
        "content_engine.Course",
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
