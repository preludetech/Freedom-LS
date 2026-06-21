"""Course application submission model (Task B.1).

The application-review-ui spec adds state machine, transitions, notes, signals,
permissions, and swaps the plain unique constraint for an active-state partial index.
The application-forms spec adds config FK and answer/file children.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class CourseApplication(SiteAwareModel):
    """A learner's request to access an application-gated course.

    Extends SiteAwareModel (UUID pk + site FK). Site isolation is automatic
    via SiteAwareManager — never filter on site_id manually.

    NOTE (review spec — application-review-ui): gains `state = FSMField(protected=True)`, the
      submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions,
      submitted_at/decided_at/decided_by, the view_application/change_application permissions,
      ApplicationNote + ApplicationStateTransition, the application_state_changed signal, and the
      active-state PARTIAL unique index that REPLACES the plain constraint below.
    NOTE (forms spec — application-forms): gains `config FK ApplicationConfig` + answer/file children.
    Do not architect these away — leave this model standalone and additive.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_applications",
    )
    course = models.ForeignKey(
        "freedom_ls_content_engine.Course",
        on_delete=models.CASCADE,
        related_name="applications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user", "course"],
                name="unique_application_per_site_user_course",
            )
        ]

    def __str__(self) -> str:
        return f"CourseApplication({self.user_id}, {self.course_id})"
