"""RecommendedCourse model.

Records a course recommended to a user, usually off the back of a form they
filled in. Deliberately minimal: the link back to the FormProgress that produced
the recommendation is drafted below but not yet live, and there is no
recommendation source, ranking or expiry. Keep this model standalone and
additive.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class RecommendedCourse(SiteAwareModel):
    """
    Course recommendations for users.
    Created when a parent fills out a form.
    """

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

    def __str__(self) -> str:
        return f"Course recommendation for {self.user.email}: {self.course.title}"
