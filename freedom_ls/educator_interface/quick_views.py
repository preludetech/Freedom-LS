"""Quick views for the Learners and Cohorts sections.

Each drawer reads only what its own template needs -- the learner's cohort
memberships and course registrations, or the cohort's learner count and
courses -- scoped the same way the section's own list already is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.db.models import Max

from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.learner_management.queries import cohorts_visible_to
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import registrations_with_progress_for_learner
from freedom_ls.panel_framework.quick_view import QuickView

if TYPE_CHECKING:
    from freedom_ls.educator_interface.views import OrganisationScopedRequest


class LearnerQuickView(QuickView):
    template_name = "educator_interface/quick_views/learner.html"
    refresh_events = (LEARNER_CHANGED,)

    def get_title(self) -> str:
        return cast(Learner, self.instance).user.display_name

    def get_subtitle(self) -> str:
        return cast(Learner, self.instance).user.email

    def get_context_data(self) -> dict[str, object]:
        learner = cast(Learner, self.instance)
        request = cast("OrganisationScopedRequest", self.request)
        visible_cohorts = cohorts_visible_to(request.user, request.organisation)
        memberships = (
            CohortMembership.objects.filter(learner=learner, cohort__in=visible_cohorts)
            .select_related("cohort")
            .order_by("cohort__name")
        )
        last_active = CourseProgress.objects.filter(learner=learner).aggregate(
            latest=Max("last_accessed_time")
        )["latest"]
        # A registration through a cohort the educator cannot see would name
        # that cohort, so only individual ones and visible cohorts' are kept.
        visible_cohort_ids = set(visible_cohorts.values_list("pk", flat=True))
        registrations = [
            registration
            for registration in registrations_with_progress_for_learner(learner)
            if registration.cohort is None
            or registration.cohort.pk in visible_cohort_ids
        ]
        return {
            # The template reads learner.is_active directly for the Status
            # line, showing "Active" or "Removed" -- a placeholder until
            # learner administration adds a genuine "pending" state.
            "learner": learner,
            "memberships": memberships,
            "registrations": registrations,
            "last_active": last_active,
        }


class CohortQuickView(QuickView):
    template_name = "educator_interface/quick_views/cohort.html"
    refresh_events = (COHORT_CHANGED,)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        return {
            "cohort": cohort,
            "learner_count": cohort.cohortmembership_set.count(),
            "courses": [
                registration.course
                for registration in cohort.course_registrations.select_related("course")
            ],
        }
