"""ApplicationCourseAccessBackend — the application-gating access backend.

Subclasses FreeOnlyCourseAccessBackend from course_access. This is the only new
inter-app edge: course_applications → course_access. course_access never imports
course_applications.

This is the shipped default COURSE_ACCESS_BACKEND.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import reverse

from freedom_ls.course_access.backends import (
    CourseAccessDecision,
    DashboardContribution,
    FreeOnlyCourseAccessBackend,
)
from freedom_ls.student_management.utils import is_registered_for_course

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication

    type RequestUser = User | AnonymousUser


# ---------------------------------------------------------------------------
# Application-gated access type (extends core vocabulary, not part of CourseAccessType)
# ---------------------------------------------------------------------------

APPLICATION_GATED = "application_gated"
"""Access type for courses that require a learner application before enrolment.

This value is intentionally NOT added to core's CourseAccessType — it belongs
to the applications backend. Core (course_access, student_interface) never
references this string.
"""


class ApplicationCourseAccessBackend(FreeOnlyCourseAccessBackend):
    """Application-gating access backend.

    Extends FreeOnlyCourseAccessBackend to add the application_gated access type,
    the "Apply now" CTA, and the in-flight-applications dashboard panel.

    Core (course_access, student_interface) remains ignorant of applications —
    the course_applications → course_access edge is the only arrow, and it is
    acyclic.
    """

    # Widen the accepted access-type vocabulary; the inherited
    # validate_course_config reads this through self, so no override is needed.
    _ALLOWED_ACCESS_TYPES = frozenset({"free", APPLICATION_GATED})

    # filter_visible is deliberately NOT overridden: gated courses stay discoverable
    # in listings. Gating is enforced at the CTA + initiate_course_access chokepoint,
    # not by hiding courses.

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        """Return a CourseAccessDecision for this user + course.

        Registered → Continue/content (inherited from parent). A learner enrolled
        into a gated course by an admin or via a cohort therefore reaches content:
        admin/cohort enrolment deliberately bypasses the gate.
        Free, not registered → Start/self-register (inherited from parent).
        Application-gated, not registered → Apply now / apply URL.
        Invalid config → safe no-action decision (inherited from parent).
        """
        try:
            config = self.validate_course_config(course.access_config)
        except ValueError:
            return CourseAccessDecision(
                cta_label=None,
                cta_url=None,
                can_self_register=False,
                can_access_content=False,
            )

        # Delegate to parent for free-course handling AND for any registered
        # learner — including one enrolled into a gated course by admin/cohort,
        # who must reach content (registered → Continue/content). Only an
        # unregistered learner on a gated course falls through to "Apply now".
        # Parent's get_access also calls validate_course_config, but that's
        # a cheap call and keeps the delegation simple.
        if config["access_type"] != APPLICATION_GATED or is_registered_for_course(
            user, course
        ):
            return super().get_access(user=user, course=course)

        # application_gated branch. A returning applicant gets a CTA straight to
        # their status page; a first-time visitor gets "Apply now".
        from freedom_ls.course_applications.queries import get_application_for_course

        existing_app = get_application_for_course(user=user, course=course)
        if existing_app is not None:
            return CourseAccessDecision(
                cta_label="View my application",
                cta_url=reverse(
                    "course_applications:status",
                    kwargs={"pk": existing_app.pk},
                ),
                can_self_register=False,
                can_access_content=False,
                enrolment_summary="By application",
                acquisition_heading="Application required",
                acquisition_subtext="Apply and we'll review your request.",
            )

        return CourseAccessDecision(
            cta_label="Apply now",
            cta_url=reverse(
                "course_applications:apply",
                kwargs={"course_slug": course.slug},
            ),
            can_self_register=False,
            can_access_content=False,
            enrolment_summary="By application",
            acquisition_heading="Application required",
            acquisition_subtext="Apply and we'll review your request.",
        )

    def get_dashboard_contributions(
        self, *, user: RequestUser
    ) -> list[DashboardContribution]:
        """Return in-flight-application panel if the learner has any applications.

        student_interface renders each contribution generically via render_to_string
        and never reads context keys — it never imports course_applications.
        """
        from freedom_ls.course_applications.queries import get_active_applications

        # Materialise once to avoid a second DB hit when the template iterates.
        apps: list[CourseApplication] = list(get_active_applications(user))
        if not apps:
            return []

        return [
            DashboardContribution(
                template_name="course_applications/partials/dashboard_applications.html",
                context={"applications": apps},
            )
        ]
