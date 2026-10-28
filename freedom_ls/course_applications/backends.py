"""ApplicationCourseAccessBackend — the application-gating access backend.

Subclasses FreeOnlyCourseAccessBackend from course_access. This is the only new
inter-app edge: course_applications → course_access. course_access never imports
course_applications.

This is the shipped default COURSE_ACCESS_BACKEND.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.paginator import Page, Paginator
from django.urls import reverse

from freedom_ls.base.pagination import clamped_page, position_text
from freedom_ls.course_access.backends import (
    AccessBadge,
    CourseAccessDecision,
    CourseAccessType,
    DashboardContribution,
    FreeOnlyCourseAccessBackend,
)
from freedom_ls.learner_management.utils import is_registered_for_course

if TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpRequest

    from freedom_ls.accounts.models import User
    from freedom_ls.content_engine.models import Course
    from freedom_ls.course_applications.models import CourseApplication

    type RequestUser = User | AnonymousUser


# ---------------------------------------------------------------------------
# Application-gated access type
# ---------------------------------------------------------------------------

# Access type for courses that require a learner application before enrolment.
# Intentionally not added to core's CourseAccessType — it belongs to the
# applications backend, and core (course_access, learner_interface) never
# references this string.
APPLICATION_GATED = "application_gated"

# The dashboard panel shows this many applications at a time. The page lives in
# its own query parameter so paging it leaves every course section's page alone.
# The swap id is what the pager targets; the dashboard view reads it back from
# HX-Target and answers such a request with the panel alone, so this backend
# tells a swap of its own panel from any other request the same way.
APPLICATIONS_PAGE_SIZE = 3
APPLICATIONS_PAGE_PARAM = "page_applications"
APPLICATIONS_SWAP_ID = "applications-page"
APPLICATIONS_PANEL_TEMPLATE = "course_applications/partials/dashboard_applications.html"


class ApplicationCourseAccessBackend(FreeOnlyCourseAccessBackend):
    """Application-gating access backend.

    Extends FreeOnlyCourseAccessBackend to add the application_gated access type,
    the "Apply now" CTA, and the in-flight-applications dashboard panel.

    Core (course_access, learner_interface) remains ignorant of applications —
    the course_applications → course_access edge is the only arrow, and it is
    acyclic.
    """

    # Widen the accepted access-type vocabulary; the inherited
    # validate_course_config reads this through self, so no override is needed.
    _ALLOWED_ACCESS_TYPES = frozenset({"free", APPLICATION_GATED})

    # application_form is this backend's key: the path, relative to course.md, of
    # the FORM an applicant fills in. The content loader resolves it and binds
    # Course.application_form; nothing at runtime reads it back out of the config.
    _ALLOWED_CONFIG_KEYS = frozenset({"access_type", "application_form"})

    # filter_visible is deliberately NOT overridden: gated courses stay discoverable
    # in listings. Gating is enforced at the CTA + initiate_course_access chokepoint,
    # not by hiding courses.

    def validate_course_config(
        self,
        raw: dict[str, Any],
        *,
        file_path: str = "",
    ) -> dict[str, Any]:
        """Add the application_form rules on top of the inherited structural checks.

        Nested inside the access_config JSON blob, application_form gets none of
        the pydantic coercion a top-level schema field would give it, so its type
        is checked here. Naming a form on a course that is not gated is an
        authoring mistake rather than a harmless extra, so it is refused.
        """
        config = super().validate_course_config(raw, file_path=file_path)

        if "application_form" not in config:
            return config

        context = f" in {file_path!r}" if file_path else ""
        form_path = config["application_form"]
        if not isinstance(form_path, str) or not form_path.strip():
            raise ValueError(
                f"Course access_config has an invalid application_form="
                f"{form_path!r}{context}. Expected a path to a FORM file, "
                f"relative to course.md."
            )
        if config["access_type"] != APPLICATION_GATED:
            raise ValueError(
                f"Course access_config names an application_form{context} but has "
                f"access_type={config['access_type']!r}. application_form is only "
                f"valid with access_type={APPLICATION_GATED!r}."
            )
        return config

    def get_access(self, *, user: RequestUser, course: Course) -> CourseAccessDecision:
        """Return a CourseAccessDecision for this user + course.

        Registered → Continue/content (inherited from parent). A learner enrolled
        into a gated course by an admin or via a cohort therefore reaches content:
        admin/cohort enrolment deliberately bypasses the gate.
        Free, not registered → Enrol for free/self-register (inherited from parent).
        Application-gated, not registered → View my application when one exists,
        otherwise Apply now.
        Invalid config → safe no-action decision.
        """
        decision = self._ungated_decision(user=user, course=course)
        if decision is not None:
            return decision
        from freedom_ls.course_applications.queries import get_application_for_course

        return self._gated_decision(
            course=course,
            application=get_application_for_course(user=user, course=course),
        )

    def get_access_for_request(
        self, *, request: HttpRequest, course: Course
    ) -> CourseAccessDecision:
        """Like get_access, but an anonymous session that holds an application for
        the course is sent to it the way a signed-in applicant is."""
        if request.user.is_authenticated:
            return self.get_access(user=request.user, course=course)
        decision = self._ungated_decision(user=request.user, course=course)
        if decision is not None:
            return decision
        from freedom_ls.course_applications.anonymous_session import (
            anonymous_applicant_for_course,
            application_of,
        )

        applicant = anonymous_applicant_for_course(request, course)
        application = application_of(applicant) if applicant is not None else None
        return self._gated_decision(course=course, application=application)

    def _ungated_decision(
        self, *, user: RequestUser, course: Course
    ) -> CourseAccessDecision | None:
        """The decision when the gate does not apply: invalid config, a free
        course or a registered learner. None leaves it to the gated branch."""
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
        # unregistered learner on a gated course falls through to the gate.
        # Parent's get_access also calls validate_course_config, but that's
        # a cheap call and keeps the delegation simple.
        if config["access_type"] != APPLICATION_GATED or is_registered_for_course(
            user, course
        ):
            return super().get_access(user=user, course=course)
        return None

    def _gated_decision(
        self, *, course: Course, application: CourseApplication | None
    ) -> CourseAccessDecision:
        """ "View my application" for an applicant, "Apply now" for anyone else."""
        if application is not None:
            return CourseAccessDecision(
                cta_label="View my application",
                cta_url=reverse(
                    "course_applications:status",
                    kwargs={"pk": application.pk},
                ),
                can_self_register=False,
                can_access_content=False,
                enrolment_summary="By application",
                acquisition_heading="Application required",
                acquisition_subtext="Apply and we'll review your request.",
                is_accessible_for_free=False,
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
            is_accessible_for_free=False,
        )

    def is_accessible_for_free(self, *, course: Course) -> bool:
        """Free unless the course is application-gated — config-only, no queries.

        Mirrors the is_accessible_for_free field get_access sets on the gated
        branches; invalid config falls back to True (the CourseAccessDecision default).
        """
        try:
            config = self.validate_course_config(course.access_config)
        except ValueError:
            return True
        # access_config values are typed Any (opaque JSON); coerce to bool.
        return bool(config["access_type"] != APPLICATION_GATED)

    def get_access_badge(self, *, course: Course) -> AccessBadge | None:
        """Free courses read "Free"; application-gated courses read "By application".

        Reuses the config-only is_accessible_for_free so the free/gated decision
        lives in one place.
        """
        if self.is_accessible_for_free(course=course):
            return AccessBadge(label="Free")
        return AccessBadge(label="By application")

    def get_access_type(self, *, course: Course) -> str:
        """The course's configured access type; invalid config reads as free,
        the same fallback is_accessible_for_free takes."""
        try:
            config = self.validate_course_config(course.access_config)
        except ValueError:
            return str(CourseAccessType.FREE)
        return str(config["access_type"])

    def get_dashboard_contributions(
        self, *, user: RequestUser
    ) -> list[DashboardContribution]:
        """Page one of the learner's applications: with no request there is no page to read.

        learner_interface renders each contribution generically via render_to_string
        and never reads context keys — it never imports course_applications.
        """
        from freedom_ls.course_applications.queries import get_active_applications

        page = Paginator(
            get_active_applications(user), APPLICATIONS_PAGE_SIZE
        ).get_page(1)
        return self._applications_panel(page, own_swap=False)

    def get_dashboard_contributions_for_request(
        self, *, request: HttpRequest
    ) -> list[DashboardContribution]:
        """The signed-in user's applications, or the drafts an anonymous session holds, paged.

        A visitor sees only what their browser can still act on: a submitted
        application waits for the claim link, so it is not listed here.
        """
        if request.user.is_authenticated:
            from freedom_ls.course_applications.queries import get_active_applications

            applications = get_active_applications(request.user)
        else:
            from freedom_ls.course_applications.anonymous_session import (
                owned_applications,
            )

            # An empty session map makes this an `IN ()` filter, which Django
            # answers without a query.
            applications = (
                owned_applications(request)
                .filter(
                    form_progress__isnull=False,
                    form_progress__completed_time__isnull=True,
                )
                .select_related("course", "form_progress")
                .order_by("-created_at", "pk")
            )
        # The paginator counts and then fetches one page, so only the three
        # rows shown ever leave the database.
        page = clamped_page(
            request, APPLICATIONS_PAGE_PARAM, applications, APPLICATIONS_PAGE_SIZE
        )
        own_swap = request.headers.get("HX-Target") == APPLICATIONS_SWAP_ID
        return self._applications_panel(page, own_swap=own_swap)

    def _applications_panel(
        self, page: Page[CourseApplication], *, own_swap: bool
    ) -> list[DashboardContribution]:
        """The panel, or nothing when the learner has no applications to show.

        A swap of the panel's own page gets the page fragment rather than the
        whole panel, and gets it even when nothing is left: the fragment then
        empties the panel in place. Only that swap announces its position; a
        whole-page load already puts the heading and the position text in
        front of the reader.
        """
        if page.paginator.count == 0 and not own_swap:
            return []
        template_name = APPLICATIONS_PANEL_TEMPLATE
        if own_swap:
            template_name += "#panel-page-response"
        return [
            DashboardContribution(
                template_name=template_name,
                context={
                    "applications": list(page.object_list),
                    "applications_page": page,
                    "position_text": position_text(page),
                    "announce_page": own_swap,
                    "swap_id": APPLICATIONS_SWAP_ID,
                    "page_param_name": APPLICATIONS_PAGE_PARAM,
                },
                swap_id=APPLICATIONS_SWAP_ID,
            )
        ]
