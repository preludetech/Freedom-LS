"""The learner quick view and the registrations it lists."""

from __future__ import annotations

from typing import cast
from uuid import uuid4

from django.db.models import Max

from freedom_ls.comms.config import config as comms_config
from freedom_ls.comms.messaging_views import message_box_context
from freedom_ls.educator_interface.events import LEARNER_CHANGED
from freedom_ls.educator_interface.messaging import own_conversation_with
from freedom_ls.educator_interface.panels.common.badges import learner_status_badge
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.educator_interface.user_display import email_below_name
from freedom_ls.learner_management.models import CohortMembership, Learner
from freedom_ls.learner_management.queries import cohorts_visible_to
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.learner_progress.queries import (
    LearnerRegistrationProgress,
    registrations_with_progress_for_learner,
)
from freedom_ls.panel_framework.quick_view import QuickView

__all__ = ["LearnerQuickView", "visible_registrations_with_progress"]


def visible_registrations_with_progress(
    learner: Learner, request: OrganisationScopedRequest
) -> list[LearnerRegistrationProgress]:
    """The learner's active registrations with progress, minus any made
    through a cohort the educator cannot see: such a row would name that
    cohort."""
    visible_cohort_ids = set(
        cohorts_visible_to(request.user, request.organisation).values_list(
            "pk", flat=True
        )
    )
    return [
        registration
        for registration in registrations_with_progress_for_learner(learner)
        if registration.cohort is None or registration.cohort.pk in visible_cohort_ids
    ]


class LearnerQuickView(QuickView):
    template_name = "educator_interface/quick_views/learner.html"
    refresh_events = (LEARNER_CHANGED,)

    def get_title(self) -> str:
        return cast(Learner, self.instance).user.display_name

    def get_subtitle(self) -> str:
        return email_below_name(cast(Learner, self.instance).user)

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
        registrations = visible_registrations_with_progress(learner, request)
        context: dict[str, object] = {
            "learner": learner,
            "status_badge": learner_status_badge(learner),
            "memberships": memberships,
            "registrations": registrations,
            "last_active": last_active,
        }
        if comms_config.MESSAGING_ENABLED:
            context.update(self._message_box_context(learner))
        return context

    def _message_box_context(self, learner: Learner) -> dict[str, object]:
        """The message box for the educator and learner, or nothing when the
        policy refuses. A refused pair gets no box at all.

        The box's "Open conversation" link goes to the learner page's Messages
        tab, which exists before the first message does.
        """
        request = cast("OrganisationScopedRequest", self.request)
        own = own_conversation_with(request, learner)
        if not own.allowed:
            return {}
        return {
            "message_box": True,
            "open_url": interface_path(
                request.organisation, f"learners/{learner.pk}/__tabs/messages"
            ),
            **message_box_context(
                conversation=own.conversation,
                other=learner.user,
                client_key=uuid4(),
                recipient=learner.user if own.conversation is None else None,
            ),
        }
