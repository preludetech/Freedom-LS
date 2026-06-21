"""ApplicationCourseAccessBackend — the application-gating access backend (Task B.6).

Subclasses DefaultCourseAccessBackend from course_access. This is the only new
inter-app edge: course_applications → course_access. course_access never imports
course_applications.

This is the shipped default COURSE_ACCESS_BACKEND (Task 0.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.urls import reverse

from freedom_ls.course_access.backends import (
    CourseAccessDecision,
    DashboardContribution,
    DefaultCourseAccessBackend,
)

if TYPE_CHECKING:
    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course


# ---------------------------------------------------------------------------
# Application-gated access type (extends core vocabulary, not part of CourseAccessType)
# ---------------------------------------------------------------------------

APPLICATION_GATED = "application_gated"
"""Access type for courses that require a learner application before enrolment.

This value is intentionally NOT added to core's CourseAccessType — it belongs
to the applications backend. Core (course_access, student_interface) never
references this string.
"""


class ApplicationCourseAccessBackend(DefaultCourseAccessBackend):
    """Application-gating access backend.

    Extends DefaultCourseAccessBackend to add the application_gated access type,
    the "Apply now" CTA, and the in-flight-applications dashboard panel.

    Core (course_access, student_interface) remains ignorant of applications —
    the course_applications → course_access edge is the only arrow, and it is
    acyclic.
    """

    # Accepted access type values for this backend
    _ALLOWED_ACCESS_TYPES = {"free", APPLICATION_GATED}

    def validate_course_config(
        self,
        # Deliberate Any: access_config is a genuinely opaque JSON blob whose
        # keys are backend-owned; this backend's validate_course_config is the
        # one implementation for all callers.
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Accept access_type ∈ {free, application_gated}; absent → free.

        Rejects unknown keys and unknown access_type values with file_path context.
        Returns the normalised dict {"access_type": <value>}.
        """
        allowed_keys = {"access_type"}
        extra_keys = set(raw.keys()) - allowed_keys
        if extra_keys:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has unknown key(s){context}: "
                f"{sorted(extra_keys)!r}. Allowed keys: {sorted(allowed_keys)!r}"
            )

        access_type = raw.get("access_type", "free")
        if access_type not in self._ALLOWED_ACCESS_TYPES:
            context = f" in {file_path!r}" if file_path else ""
            raise ValueError(
                f"Course access_config has invalid access_type={access_type!r}{context}. "
                f"Valid values for this backend: {sorted(self._ALLOWED_ACCESS_TYPES)!r}."
            )
        return {"access_type": access_type}

    def get_access(self, *, user: User, course: Course) -> CourseAccessDecision:
        """Return a CourseAccessDecision for this user + course.

        Registered → Continue/content (inherited from parent).
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

        # Delegate to parent for registered learners and free-course handling.
        # Parent's get_access also calls validate_course_config, but that's
        # a cheap call and keeps the delegation simple.
        if config["access_type"] != APPLICATION_GATED:
            return super().get_access(user=user, course=course)

        # application_gated branch
        # Keep "Apply now" for both first-time and returning applicants — the
        # apply view (B.4) redirects an in-flight applicant to their status page,
        # so a single label satisfies the re-apply rule (spec §5.2) and the QA flow.
        return CourseAccessDecision(
            cta_label="Apply now",
            cta_url=reverse(
                "course_applications:apply",
                kwargs={"course_slug": course.slug},
            ),
            can_self_register=False,
            can_access_content=False,
        )

    def get_dashboard_contributions(self, *, user: User) -> list[DashboardContribution]:
        """Return in-flight-application panel if the learner has any applications.

        student_interface renders each contribution generically via render_to_string
        and never reads context keys — it never imports course_applications.
        """
        from freedom_ls.course_applications.queries import get_active_applications

        # Materialise once to avoid a second DB hit when the template iterates.
        apps: list = list(get_active_applications(user))
        if not apps:
            return []

        return [
            DashboardContribution(
                template_name="course_applications/partials/dashboard_applications.html",
                context={"applications": apps},
            )
        ]
