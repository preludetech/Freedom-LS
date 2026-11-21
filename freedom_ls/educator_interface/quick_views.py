"""Quick views for the Learners and Cohorts sections.

Each drawer reads only what its own template needs -- the learner's cohort
memberships and course registrations, or the cohort's learner count and
courses -- scoped the same way the section's own list already is.
"""

from __future__ import annotations

from typing import cast

from freedom_ls.educator_interface.events import (
    COHORT_CHANGED,
)
from freedom_ls.educator_interface.panels.common.badges import (
    active_status_badge,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.learner_management.models import Cohort
from freedom_ls.learner_management.queries import (
    cohort_learner_count,
)
from freedom_ls.panel_framework.quick_view import QuickView


class CohortQuickView(QuickView):
    template_name = "educator_interface/quick_views/cohort.html"
    refresh_events = (COHORT_CHANGED,)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        request = cast("OrganisationScopedRequest", self.request)
        return {
            "cohort": cohort,
            "status_badge": active_status_badge(cohort.is_active),
            "learner_count": cohort_learner_count(cohort),
            "courses": [
                registration.course.label_for(request.organisation)
                for registration in cohort.course_registrations.filter(is_active=True)
                .select_related("course")
                .prefetch_related("course__organisations")
            ],
        }
