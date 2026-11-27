"""The attempt review page: one completed quiz sitting of one learner.

A sitting is reached from the learner's Courses tab, so the section has no
list and stays out of the menu.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from panel_framework.lazy_panels import LazyBodyPanel
from panel_framework.panels import InstanceDetailsPanel, PanelStack
from panel_framework.quick_view import QuickView
from panel_framework.views import HeaderStat, InstanceView, ListViewConfig

from django.db.models import F, Model, prefetch_related_objects
from django.http import HttpRequest

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import Course
from freedom_ls.educator_interface.exceptions import OrganisationScopeDenied
from freedom_ls.educator_interface.panels.common.question_detail import (
    question_detail_withheld_note,
)
from freedom_ls.educator_interface.panels.common.request import (
    OrganisationScopedRequest,
    OrganisationSectionConfig,
)
from freedom_ls.educator_interface.panels.learner.quick_view import (
    visible_registrations_with_progress,
)
from freedom_ls.educator_interface.paths import interface_path
from freedom_ls.form_engine.conditions import (
    SERVED_TREE_LOOKUPS,
    SittingPath,
    answers_by_question,
    sitting_path,
)
from freedom_ls.form_engine.models import (
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionAnswer,
    marking_options,
)
from freedom_ls.form_engine.queries import format_quiz_time_limit, stored_score_outdated
from freedom_ls.form_engine.scoring import is_quiz_answer_correct
from freedom_ls.learner_management.capabilities import record_question_view
from freedom_ls.learner_management.models import Learner
from freedom_ls.learner_management.queries import learners_visible_to
from freedom_ls.learner_progress.models import CourseFormAttempt
from freedom_ls.learner_progress.queries import LearnerRegistrationProgress
from freedom_ls.reports.gather import attempt_number_of, score_attempt

__all__ = [
    "QuestionMark",
    "QuestionVerdict",
    "QuizAttemptConfig",
    "QuizAttemptFacts",
    "QuizAttemptInstanceView",
    "QuizAttemptPaperPanel",
    "QuizAttemptQuickView",
    "QuizAttemptResult",
    "QuizAttemptStack",
    "QuizAttemptSummaryPanel",
    "openable_sitting_ids",
    "quiz_attempt_facts",
    "quiz_attempt_paper_context",
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


_FACTS_CACHE_ATTR = "_quiz_attempt_facts_cache"


def quiz_attempt_facts(sitting: FormProgress) -> QuizAttemptFacts:
    """Who sat what, on which course, as which attempt. Raises ValueError
    for a sitting with no number: one that never passed authorise_instance.

    Cached on the sitting, so the page title, back link, subtitle and quick
    view of one request share a single lookup.
    """
    cached = sitting.__dict__.get(_FACTS_CACHE_ATTR)
    if isinstance(cached, QuizAttemptFacts):
        return cached
    attempt = CourseFormAttempt.objects.select_related(
        "course_progress__learner__user",
        "course_progress__learner__organisation",
        "course_progress__course",
    ).get(form_progress=sitting)
    number = attempt_number_of(sitting)
    if number is None:
        raise ValueError(f"Sitting {sitting.pk} has no attempt number")
    facts = QuizAttemptFacts(
        sitting=sitting,
        learner=attempt.course_progress.learner,
        course=attempt.course_progress.course,
        attempt_number=number,
    )
    sitting.__dict__[_FACTS_CACHE_ATTR] = facts
    return facts


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
    """When the sitting started and finished, why it finished, the time limit it
    ran under, and the pass mark it is judged against today. The score and verdict
    are in the page header."""

    model = FormProgress
    title = "Summary"

    def get_rows(self) -> list[dict[str, object]]:
        sitting = cast(FormProgress, self.instance)
        pass_percentage = sitting.form.quiz_pass_percentage
        rows = [
            self.detail_row("Started", sitting.start_time, "datetime"),
            self.detail_row("Completed", sitting.completed_time, "datetime"),
            self.detail_row(
                "Completion reason", sitting.get_completion_reason_display()
            ),
        ]
        # The limit recorded on the sitting, not the quiz's current one.
        if sitting.time_limit_minutes is not None:
            rows.append(
                self.detail_row(
                    "Time limit", format_quiz_time_limit(sitting.time_limit_minutes)
                )
            )
        rows.append(
            self.detail_row(
                "Pass mark (current setting)",
                "No pass mark" if pass_percentage is None else f"{pass_percentage}%",
            )
        )
        return rows


QuestionVerdict = Literal["correct", "incorrect", "not_marked"]


@dataclass(frozen=True)
class QuestionMark:
    verdict: QuestionVerdict
    answered: bool


def _mark(
    question: FormQuestion,
    answers: Mapping[UUID, QuestionAnswer],
    path: SittingPath,
) -> QuestionMark:
    """How the sitting's answer to `question` is marked today, and whether
    there is an answer at all. Reads only the prefetched answers and options.

    Judged against the options the recomputed score uses, so the mark agrees
    with what `stored_score_outdated` compares against: an option added since
    the sitting counts, and a retired option it was never served does not."""
    options = marking_options(question, path)
    answer = answers.get(question.id)
    selected_ids = (
        {option.id for option in answer.selected_options.all()} if answer else set()
    )
    answered = answer is not None and bool(
        selected_ids or answer.text_answer or hasattr(answer, "answer_file")
    )
    if not any(option.correct is True for option in options):
        verdict: QuestionVerdict = "not_marked"
    elif is_quiz_answer_correct(selected_ids, options):
        verdict = "correct"
    else:
        verdict = "incorrect"
    return QuestionMark(verdict=verdict, answered=answered)


def quiz_attempt_paper_context(sitting: FormProgress) -> dict[str, object]:
    """Every page of the sitting's path with its children, the learner's
    answers and a mark per question.

    The path is the only source of pages, children, option order and
    numbering, so the review stays right when what a path holds changes.
    """
    # Options for every question in one query, so marking a sitting with no
    # served paper costs no more queries than one with.
    prefetch_related_objects([sitting.form], *SERVED_TREE_LOOKUPS)
    answers = answers_by_question(sitting)
    prefetch_related_objects(list(answers.values()), "answer_file")
    path = sitting_path(sitting, answers)
    return {
        "paper_pages": [
            {
                "position": position,
                "page": page,
                "page_children": path.children_of(page),
            }
            for position, page in enumerate(path.pages, start=1)
        ],
        "total_pages": path.page_count,
        "sitting_path": path,
        "question_positions": path.question_positions(),
        "existing_answers": answers,
        "show_answer_key": True,
        "question_marks": {q.id: _mark(q, answers, path) for q in path.questions()},
        # Marks read every current option, so an option added since the
        # sitting is listed too, or a changed mark would have no visible cause.
        "options_added_since": {
            q.id: added
            for q in path.questions()
            if (added := path.options_added_since(q))
        },
        "score_outdated": stored_score_outdated(sitting, path, answers),
        "has_missing_served_items": path.has_missing_served_items,
        "predates_served_order": sitting.served_paper is None,
    }


class QuizAttemptPaperPanel(LazyBodyPanel):
    """The paper as this sitting was served, with the learner's answers and
    how each question is marked now.

    The paper loads only on the page's own htmx request, and each load is
    recorded against the sitting and the learner, so the paper is never
    computed for anyone who may not see it.
    """

    model = FormProgress
    title = "Paper"
    load_label = "Load the paper"
    region_template_name = "educator_interface/panels/quiz_attempt_paper_region.html"
    skeleton_lines = 8

    def get_loaded_context(self) -> dict[str, object]:
        sitting = cast(FormProgress, self.instance)
        learner = quiz_attempt_facts(sitting).learner
        note = question_detail_withheld_note(self.request, learner.organisation)
        if note:
            return {"question_detail_note": note}
        record_question_view(
            actor=cast(User, self.request.user),
            target=sitting,
            target_label=QuizAttemptConfig.get_instance_label(sitting),
            organisation=learner.organisation,
            subjects=[learner],
            details={
                "surface": "attempt_review",
                "forms": [{"id": str(sitting.form.pk), "title": sitting.form.title}],
            },
        )
        return quiz_attempt_paper_context(sitting)


class QuizAttemptStack(PanelStack):
    title = "Quiz attempt"
    children = {"summary": QuizAttemptSummaryPanel, "paper": QuizAttemptPaperPanel}


class QuizAttemptInstanceView(InstanceView):
    panel = QuizAttemptStack

    @property
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
        if result.pass_percentage is None:
            verdict = "No pass mark"
        elif result.passed is None:
            verdict = "Not scored"
        else:
            verdict = "Passed" if result.passed else "Failed"
        stats.append(HeaderStat("Result", verdict))
        return stats


class QuizAttemptQuickView(QuickView):
    """The attempt's result at a glance. The header's "Open full page" icon is its one link to the review."""

    template_name = "educator_interface/quick_views/quiz_attempt.html"

    def get_title(self) -> str:
        return QuizAttemptConfig.get_instance_label(self.instance)

    def get_subtitle(self) -> str:
        return quiz_attempt_facts(
            cast(FormProgress, self.instance)
        ).learner.user.display_name

    def get_context_data(self) -> dict[str, object]:
        sitting = cast(FormProgress, self.instance)
        return {"sitting": sitting, "result": quiz_attempt_result(sitting)}


class QuizAttemptConfig(OrganisationSectionConfig, ListViewConfig):
    url_name = "quiz-attempts"
    menu_label = "Quiz attempts"
    model = FormProgress
    list_view = None
    in_menu = False
    instance_view = QuizAttemptInstanceView
    quick_view = QuizAttemptQuickView

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
