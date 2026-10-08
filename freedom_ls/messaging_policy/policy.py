"""The default messaging policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from django.db.models import Q, Value

from freedom_ls.accounts.models import User
from freedom_ls.comms.messaging_policy import (
    MessagingDecision,
    MessagingPolicy,
    MessagingRefusal,
)
from freedom_ls.learner_management.capabilities import roles_granting
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.learner_management.queries import (
    VIEW_LEARNER,
    colleagues_of,
    holds_registration_for_any_expression,
    is_in_cohort_expression,
    registrations_of,
    visible_learners_expression,
)
from freedom_ls.messaging_policy.config import config
from freedom_ls.messaging_policy.models import MessagingFlag
from freedom_ls.messaging_policy.resolver import resolved_flag_expression

if TYPE_CHECKING:
    from django.contrib.sites.models import Site
    from django.db.models import Model, QuerySet


class _Resolution(NamedTuple):
    """What one call needs about the sender, read once."""

    site: Site
    rows: list[Learner]  # the sender's active Learner rows on the site


class LayeredMessagingPolicy(MessagingPolicy):
    def can_start(
        self, *, sender: User, recipient: User, site: Site
    ) -> MessagingDecision:
        if sender == recipient:
            return MessagingDecision.refuse(MessagingRefusal.SAME_USER)
        if not (sender.is_active and recipient.is_active):
            return MessagingDecision.refuse(MessagingRefusal.INACTIVE_USER)
        resolution = self._resolve(sender, site)
        if (
            self._related_users(sender, resolution, open_only=True)
            .filter(pk=recipient.pk)
            .exists()
        ):
            return MessagingDecision.allow()
        if (
            self._related_users(sender, resolution, open_only=False)
            .filter(pk=recipient.pk)
            .exists()
        ):
            return MessagingDecision.refuse(MessagingRefusal.CLOSED_BY_CONFIGURATION)
        return MessagingDecision.refuse(MessagingRefusal.NO_RELATIONSHIP)

    def can_reply(
        self, *, sender: User, recipient: User, site: Site, conversation: Model
    ) -> MessagingDecision:
        # Reply rights are symmetric: whichever direction may start now keeps the
        # conversation open, so the conversation itself is not consulted.
        forward = self.can_start(sender=sender, recipient=recipient, site=site)
        if forward.allowed:
            return forward
        backward = self.can_start(sender=recipient, recipient=sender, site=site)
        return MessagingDecision.allow() if backward.allowed else forward

    def recipients_for(self, *, sender: User, site: Site) -> QuerySet[User]:
        if not sender.is_active:
            # can_start refuses every pair for an inactive sender.
            return User.objects.none()
        return self._related_users(sender, self._resolve(sender, site), open_only=True)

    def _resolve(self, sender: User, site: Site) -> _Resolution:
        rows = list(
            Learner.objects.filter(
                user=sender, site=site, is_active=True
            ).select_related("organisation", "site")
        )
        return _Resolution(site=site, rows=rows)

    def _related_users(
        self, sender: User, resolution: _Resolution, *, open_only: bool
    ) -> QuerySet[User]:
        """With open_only, the users the sender may start with: colleagues, learners
        the sender is an educator of, and users reached through a candidate that
        resolves open. Without it, every user any candidate reaches whatever it
        resolves to, which is what separates "closed" from "no relationship".

        Built as one queryset of pk__in subqueries so it needs no distinct() and
        stays filterable.
        """
        site = resolution.site
        roles = roles_granting(VIEW_LEARNER, site)
        visible_learners = Learner.objects.filter(site=site, is_active=True).filter(
            visible_learners_expression(sender, roles, site)
        )
        condition = Q(pk__in=visible_learners.values("user_id")) | Q(
            pk__in=colleagues_of(sender, site).values("pk")
        )
        for row in resolution.rows:
            condition |= self._candidate_users_expression(
                row, resolution, open_only=open_only
            )
        return (
            User.objects.filter(site=site, is_active=True)
            .exclude(pk=sender.pk)
            .filter(condition)
        )

    def _candidate_users_expression(
        self, row: Learner, resolution: _Resolution, *, open_only: bool
    ) -> Q:
        """One Q over User rows for every candidate this sender row produces."""
        site = resolution.site
        peer_rows = Learner.objects.filter(
            site=site, organisation_id=row.organisation_id, is_active=True
        )
        cohorts = self._resolved_cohorts(
            row, resolution, "learner_to_cohort_peer", open_only=open_only
        )
        through_shared_cohorts = peer_rows.filter(
            is_in_cohort_expression(site, cohorts.values("pk"))
        )
        own, through_cohorts = self._resolved_registrations(
            row, resolution, open_only=open_only
        )
        own_courses = own.values("course_id")
        cohort_courses = through_cohorts.values("course_id")
        through_courses = peer_rows.filter(
            holds_registration_for_any_expression(site, own_courses)
            | holds_registration_for_any_expression(site, cohort_courses)
        )
        return Q(pk__in=through_shared_cohorts.values("user_id")) | Q(
            pk__in=through_courses.values("user_id")
        )

    def _row_layers(
        self, row: Learner, resolution: _Resolution, flag: str
    ) -> dict[str, str | None]:
        """The layers that depend only on the sender row, read in Python."""
        return {"settings": config.MESSAGING_DEFAULT_FLAGS[flag]}

    def _resolved_cohorts(
        self, row: Learner, resolution: _Resolution, flag: str, *, open_only: bool
    ) -> QuerySet[Cohort]:
        """The cohorts the sender row is a member of, each resolved for `flag` through
        its own chain; with open_only, only those resolving open."""
        cohorts = Cohort.objects.filter(
            site=resolution.site, cohortmembership__learner=row
        )
        return self._keep_open(cohorts, row, resolution, flag, open_only=open_only)

    def _resolved_registrations(
        self, row: Learner, resolution: _Resolution, *, open_only: bool
    ) -> tuple[QuerySet[LearnerCourseRegistration], QuerySet[CohortCourseRegistration]]:
        """The sender row's active registrations by each path, each resolved for the
        course-peer flag through its own chain; with open_only, only those resolving
        open. Callers take values("course_id") of each."""
        own, through_cohorts = registrations_of(row)
        flag = "learner_to_course_peer"
        return (
            self._keep_open(own, row, resolution, flag, open_only=open_only),
            self._keep_open(
                through_cohorts, row, resolution, flag, open_only=open_only
            ),
        )

    def _keep_open[T: Model](
        self,
        candidates: QuerySet[T],
        row: Learner,
        resolution: _Resolution,
        flag: str,
        *,
        open_only: bool,
    ) -> QuerySet[T]:
        """`candidates` unchanged, or with open_only only those whose chain resolves
        open for `flag`."""
        if not open_only:
            return candidates
        expression = resolved_flag_expression(self._row_layers(row, resolution, flag))
        if isinstance(expression, Value):
            # The chain is a constant for every candidate, so no join is needed.
            return (
                candidates
                if expression.value == MessagingFlag.OPEN
                else candidates.none()
            )
        open_candidates: QuerySet[T] = candidates.annotate(resolved=expression).filter(
            resolved=MessagingFlag.OPEN
        )
        return open_candidates
