"""A course put in front of a user on their dashboard without registering them.

A recommendation is one row per user and course. Staff make rows in the admin;
other apps may make and remove them too. The model carries no source, ranking
or expiry, and the link to the form that could one day recommend a course is
drafted below but not live.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class RecommendedCourse(SiteAwareModel):
    """One course recommended to one user, shown in the dashboard's Recommended courses."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
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
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "course"], name="unique_recommended_course"
            )
        ]

    def __str__(self) -> str:
        return f"Course recommendation for {self.user.email}: {self.course.title}"
