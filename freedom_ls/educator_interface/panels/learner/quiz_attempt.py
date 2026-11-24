"""The attempt review page: one completed quiz sitting of one learner.

A sitting is reached from the learner's Courses tab, so the section has no
list and stays out of the menu.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import cast
from uuid import UUID

from django.db.models import F, Model
from django.http import HttpRequest

from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.learner.quick_view import (
    visible_registrations_with_progress,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.form_engine.models import FormProgress, FormStrategy
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import learners_visible_to
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.queries import LearnerRegistrationProgress
from freedom_ls.panel_framework.panels import InstanceDetailsPanel, PanelStack
from freedom_ls.panel_framework.views import HeaderStat, InstanceView, ListViewConfig
from freedom_ls.reports.gather import attempt_number_of, score_attempt

__all__ = [
    "QuizAttemptConfig",
    "QuizAttemptFacts",
    "QuizAttemptInstanceView",
    "QuizAttemptResult",
    "QuizAttemptStack",
    "QuizAttemptSummaryPanel",
    "openable_sitting_ids",
    "quiz_attempt_facts",
    "quiz_attempt_result",
]


def openable_sitting_ids(
    request: OrganisationScopedRequest,
    sitting_ids: Collection[UUID],
    shown_registrations: Mapping[UUID, Sequence[LearnerRegistrationProgress]]
    | None = None,
) -> set[UUID]:
    """The sittings among `sitting_ids` this educator may open: completed
    quiz sittings with a course form attempt, sat by the learner the course
    progress record belongs to, whom the educator sees in this organisation,
    on a registration the Courses tab shows them.

    A registration made through a cohort the educator cannot see is hidden
    on the tab, so its sittings must not open from a guessed URL either.

    `shown_registrations` maps a learner's pk to the registrations the tab
    already loaded for them, so the tab does not load them twice. The
    queries grow with the number of learners named, never with the number
    of sittings.
    """
    sittings = FormProgress.objects.filter(
        pk__in=sitting_ids,
        completed_time__isnull=False,
        form__strategy=FormStrategy.QUIZ,
        course_attempt__isnull=False,
        # The paper shows the sitting user's answers, so that user must be
        # the learner the educator was authorised to see.
        user_id=F("course_attempt__course_progress__learner__user_id"),
    ).select_related("course_attempt__course_progress__learner")
    records = {s.pk: s.course_attempt.course_progress for s in sittings}
    learners = {record.learner_id: record.learner for record in records.values()}
    visible_learner_ids = set(
        learners_visible_to(request.user, request.organisation, include_inactive=True)
        .filter(pk__in=list(learners))
        .values_list("pk", flat=True)
    )
    shown = shown_registrations or {}
    shown_registration_ids = {
        entry.registration.pk
        for learner_id in visible_learner_ids
        for entry in (
            shown[learner_id]
            if learner_id in shown
            else visible_registrations_with_progress(learners[learner_id], request)
        )
    }
    return {
        pk
        for pk, record in records.items()
        if record.learner_id in visible_learner_ids
        and (record.cohort_registration_id or record.learner_registration_id)
        in shown_registration_ids
    }


@dataclass(frozen=True)
class QuizAttemptFacts:
    sitting: FormProgress
    learner: Learner
    course: Course
    attempt_number: int


def quiz_attempt_facts(sitting: FormProgress) -> QuizAttemptFacts:
    """Who sat what, on which course, as which attempt. Raises ValueError
    for a sitting with no number: one that never passed authorise_instance."""
    attempt = CourseFormAttempt.objects.select_related(
        "course_progress__learner__user", "course_progress__course"
    ).get(form_progress=sitting)
    number = attempt_number_of(sitting)
    if number is None:
        raise ValueError(f"Sitting {sitting.pk} has no attempt number")
    return QuizAttemptFacts(
        sitting=sitting,
        learner=attempt.course_progress.learner,
        course=attempt.course_progress.course,
        attempt_number=number,
    )


@dataclass(frozen=True)
class QuizAttemptResult:
    score: int | None
    max_score: int | None
    percentage: int | None
    passed: bool | None
    pass_percentage: int | None


def quiz_attempt_result(sitting: FormProgress) -> QuizAttemptResult:
    """The stored score and the verdict against the quiz's current pass mark."""
    score, max_score, percentage, passed = score_attempt(sitting, sitting.form)
    return QuizAttemptResult(
        score=score,
        max_score=max_score,
        percentage=percentage,
        passed=passed,
        pass_percentage=sitting.form.quiz_pass_percentage,
    )


class QuizAttemptSummaryPanel(InstanceDetailsPanel):
    """When the sitting started and finished, and the pass mark it is judged
    against today. The score and verdict are in the page header."""

    model = FormProgress
    title = "Summary"

    def get_rows(self) -> list[dict[str, object]]:
        sitting = cast(FormProgress, self.instance)
        pass_percentage = sitting.form.quiz_pass_percentage
        return [
            self.detail_row("Started", sitting.start_time, "datetime"),
            self.detail_row("Completed", sitting.completed_time, "datetime"),
            self.detail_row(
                "Pass mark (current setting)",
                "No pass mark" if pass_percentage is None else f"{pass_percentage}%",
            ),
        ]


class QuizAttemptStack(PanelStack):
    title = "Quiz attempt"
    children = {"summary": QuizAttemptSummaryPanel}


class QuizAttemptInstanceView(InstanceView):
    panel = QuizAttemptStack

    @cached_property
    def facts(self) -> QuizAttemptFacts:
        return quiz_attempt_facts(cast(FormProgress, self.instance))

    def get_subtitle(self) -> str:
        learner = self.facts.learner
        subtitle = f"{learner.user.display_name} · {self.facts.course.title}"
        shared_by = self.facts.course.shared_by(learner.organisation)
        return f"{subtitle} · Shared by {shared_by}" if shared_by else subtitle

    def get_stats(self) -> list[HeaderStat]:
        result = quiz_attempt_result(self.facts.sitting)
        stats: list[HeaderStat] = []
        if result.score is not None and result.max_score is not None:
            stats.append(HeaderStat("Score", f"{result.score}/{result.max_score}"))
        if result.percentage is not None:
            stats.append(HeaderStat("Percentage", f"{result.percentage}%"))
        if result.passed is None:
            verdict = "No pass mark"
        else:
            verdict = "Passed" if result.passed else "Failed"
        stats.append(HeaderStat("Result", verdict))
        return stats


class QuizAttemptConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "quiz-attempts"
    menu_label = "Quiz attempts"
    model = FormProgress
    list_view = None
    in_menu = False
    instance_view = QuizAttemptInstanceView

    @classmethod
    def authorise_instance(cls, request: HttpRequest, instance: Model) -> None:
        scoped = cast(OrganisationScopedRequest, request)
        if instance.pk not in openable_sitting_ids(scoped, [instance.pk]):
            raise OrganisationScopeDenied

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        facts = quiz_attempt_facts(cast(FormProgress, instance))
        return f"{facts.sitting.form.title}, attempt {facts.attempt_number}"

    @classmethod
    def get_back_link(cls, request: HttpRequest, instance: Model) -> tuple[str, str]:
        facts = quiz_attempt_facts(cast(FormProgress, instance))
        organisation = cast(OrganisationScopedRequest, request).organisation
        return (
            f"Back to {facts.learner.user.display_name}",
            interface_path(organisation, f"learners/{facts.learner.pk}/__tabs/courses"),
        )
