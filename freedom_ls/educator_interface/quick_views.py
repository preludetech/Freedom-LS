"""Quick views for the Learners and Cohorts sections.

Each drawer reads only what its own template needs -- the learner's cohort
memberships and course registrations, or the cohort's learner count and
courses -- scoped the same way the section's own list already is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import uuid4

from django.db.models import Max
from django.urls import reverse

from freedom_ls.accounts.models import User
from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging import inbox_for, pair_key_for, reply_decision
from freedom_ls.comms.messaging_loader import get_messaging_policy
from freedom_ls.comms.messaging_views import message_box_context
from freedom_ls.educator_interface.events import COHORT_CHANGED, LEARNER_CHANGED
from freedom_ls.learner_management.models import Cohort, CohortMembership, Learner
from freedom_ls.learner_management.queries import (
    cohort_learner_count,
    cohorts_visible_to,
)
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import registrations_with_progress_for_learner
from freedom_ls.panel_framework.quick_view import QuickView
from freedom_ls.site_aware_models.models import get_cached_site

if TYPE_CHECKING:
    from django.contrib.sites.models import Site

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
        context: dict[str, object] = {
            # The template reads learner.is_active directly for the Status
            # line, showing "Active" or "Removed" -- a placeholder until
            # learner administration adds a genuine "pending" state.
            "learner": learner,
            "memberships": memberships,
            "registrations": registrations,
            "last_active": last_active,
        }
        if comms_config.MESSAGING_ENABLED:
            context.update(self._message_box_context(learner))
        return context

    def _message_box_context(self, learner: Learner) -> dict[str, object]:
        """The message box for the educator and learner, or nothing when the
        policy refuses.

        The policy's reply decision applies once a conversation exists, its
        start decision before then. A refused pair gets no box at all.
        """
        request = cast("OrganisationScopedRequest", self.request)
        educator = cast(User, request.user)
        conversation = (
            inbox_for(educator)
            .filter(pair_key=pair_key_for(educator, learner.user))
            .first()
        )
        if conversation is not None:
            decision = reply_decision(viewer=educator, conversation=conversation)
        else:
            decision = get_messaging_policy().can_start(
                sender=educator,
                recipient=learner.user,
                site=cast("Site", get_cached_site(request)),
            )
        if not decision.allowed:
            return {}
        # reverse() percent-encodes the braces; the page fills the pk in later.
        open_url_template = reverse(
            "educator_interface:interface",
            kwargs={
                "organisation_slug": request.organisation.slug,
                "path_string": "messages/{pk}",
            },
        ).replace("%7Bpk%7D", "{pk}")
        return {
            "message_box": True,
            "open_url_template": open_url_template,
            "open_url": open_url_template.replace("{pk}", str(conversation.pk))
            if conversation is not None
            else "",
            **message_box_context(
                conversation=conversation,
                other=learner.user,
                client_key=uuid4(),
                recipient=learner.user if conversation is None else None,
            ),
        }


class CohortQuickView(QuickView):
    template_name = "educator_interface/quick_views/cohort.html"
    refresh_events = (COHORT_CHANGED,)

    def get_context_data(self) -> dict[str, object]:
        cohort = cast(Cohort, self.instance)
        return {
            "cohort": cohort,
            "learner_count": cohort_learner_count(cohort),
            "courses": [
                registration.course
                for registration in cohort.course_registrations.filter(
                    is_active=True
                ).select_related("course")
            ],
        }
