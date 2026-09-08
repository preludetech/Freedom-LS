"""Course application submission model.

Deliberately minimal and standalone. Application review will later add a state
machine, transitions, notes, signals, and permissions, and will swap the plain
unique constraint for an active-state partial index. An application holds the
form it was created against and its own sitting of that form; the answers
themselves live in form_engine.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from freedom_ls.site_aware_models.models import SiteAwareModel


class CourseApplication(SiteAwareModel):
    """A learner's request to access an application-gated course.

    Extends SiteAwareModel (UUID pk + site FK). Site isolation is automatic
    via SiteAwareManager — never filter on site_id manually.

    NOTE: when application review lands, this model gains `state = FSMField(protected=True)`, the
      submit/withdraw/pick_up/request_changes/resubmit/approve/reject transitions,
      submitted_at/decided_at/decided_by, the view_application/change_application permissions,
      ApplicationNote + ApplicationStateTransition, the application_state_changed signal, and the
      active-state PARTIAL unique index that REPLACES the plain constraint below.
    Do not architect these away — leave this model standalone and additive.

    `form` is the form this application was made against, kept even if the course
    is later re-pointed at another one; `form_progress` is the applicant's own
    sitting of it, null when the course asks for no form.
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
    # PROTECT: deleting the form would leave applications with no record of what
    # was asked of the people who filled it in.
    form = models.ForeignKey(
        "freedom_ls_form_engine.Form",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="applications",
    )
    # SET_NULL: the application is the record that someone applied, and losing
    # the answers must not lose that.
    form_progress = models.OneToOneField(
        "freedom_ls_form_engine.FormProgress",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="course_application",
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
