"""CourseInterest model.

Records a learner's expressed interest in a coming-soon course.
Deliberately minimal. Notification support (notified_at field) will be
added via its own migration when the notify-on-launch feature is implemented
(spec §10).
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class CourseInterest(SiteAwareModel):
    """A learner's expressed interest in a coming-soon course.

    Extends SiteAwareModel (UUID pk + site FK). Site isolation is automatic
    via SiteAwareManager — never filter on site_id manually.

    NOTE: when notify-on-launch lands, this model gains a `notified_at` DateTimeField
      (null=True) to record when the learner was emailed. Do not architect this away —
      leave this model standalone and additive.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_interests",
    )
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="interests",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"], name="unique_course_interest"
            )
        ]

    def __str__(self) -> str:
        return f"CourseInterest({self.user_id}, {self.course_id})"
