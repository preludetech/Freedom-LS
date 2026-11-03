"""Which pages, questions and content blocks a sitting is asked.

A page, content block or question can carry a `condition_option`: it is asked
only when the learner selected that option on an earlier, itself asked,
question. `SittingPath` is the answer to "what is this sitting asked", and
views, admin and exports all read it instead of walking the form themselves.

Imported by views, admin and exports, never by `models` at module level.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from django.db.models import prefetch_related_objects

from .models import (
    Form,
    FormContent,
    FormPage,
    FormProgress,
    FormQuestion,
    QuestionAnswer,
    QuestionOption,
)

type FormChild = FormContent | FormQuestion

FORM_TREE_LOOKUPS = (
    "pages__condition_option",
    "pages__questions__condition_option",
    "pages__text_items__condition_option",
)


@dataclass(frozen=True, eq=False)
class SittingPath:
    """The pages, questions and content blocks one sitting is asked, in authored order.

    Page numbers are authored indexes (the URL's numbers); positions are places
    among the on-path pages (what the learner reads). The two only coincide
    when nothing is skipped.
    """

    all_pages: tuple[FormPage, ...]
    # On-path page id -> its on-path children, in page order.
    children_by_page: Mapping[UUID, tuple[FormChild, ...]]
    question_ids: frozenset[UUID]
    content_ids: frozenset[UUID]
    _page_positions: dict[int, int] = field(init=False, repr=False)
    _question_positions: dict[UUID, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        on_path_numbers = [number for number, _ in self.numbered_pages()]
        object.__setattr__(
            self,
            "_page_positions",
            {number: position for position, number in enumerate(on_path_numbers, 1)},
        )
        object.__setattr__(
            self,
            "_question_positions",
            {
                question.id: position
                for position, question in enumerate(self.questions(), start=1)
            },
        )

    def numbered_pages(self) -> list[tuple[int, FormPage]]:
        """(authored number, page) for each on-path page, in order."""
        return [
            (number, page)
            for number, page in enumerate(self.all_pages, start=1)
            if page.id in self.children_by_page
        ]

    @property
    def pages(self) -> list[FormPage]:
        return [page for _, page in self.numbered_pages()]

    @property
    def page_count(self) -> int:
        return len(self.children_by_page)

    def has_page_number(self, number: int) -> bool:
        return number in self._page_positions

    def has_question(self, question_id: UUID) -> bool:
        return question_id in self.question_ids

    def children_of(self, page: FormPage) -> list[FormChild]:
        return list(self.children_by_page.get(page.id, ()))

    def questions_of(self, page: FormPage) -> list[FormQuestion]:
        return [
            child
            for child in self.children_by_page.get(page.id, ())
            if isinstance(child, FormQuestion)
        ]

    def questions(self) -> list[FormQuestion]:
        """Every on-path question, in sitting order."""
        return [question for page in self.pages for question in self.questions_of(page)]

    def page_position(self, number: int) -> int:
        """The 1-based place of an on-path page among the on-path pages."""
        return self._page_positions[number]

    def question_positions(self) -> dict[UUID, int]:
        """The 1-based place of each on-path question among the on-path questions."""
        return self._question_positions

    def next_page_number(self, after: int) -> int | None:
        return next((n for n in self._page_positions if n > after), None)

    def previous_page_number(self, before: int) -> int | None:
        return next((n for n in reversed(self._page_positions) if n < before), None)

    def first_page_number_at_or_after(self, number: int) -> int | None:
        return next((n for n in self._page_positions if n >= number), None)

    def last_page_number(self) -> int | None:
        """The last on-path page; None only for a form with no pages."""
        return next(reversed(self._page_positions), None)

    def landing_page_number(self, number: int) -> int | None:
        """Where a request for an off-path page lands: the next on-path page, else the last."""
        following = self.next_page_number(number)
        return following if following is not None else self.last_page_number()

    def as_asked(self) -> dict[str, list[str]]:
        """The path as the string uuids a completed sitting records."""
        return {
            "pages": [str(page.id) for page in self.pages],
            "questions": [str(question.id) for question in self.questions()],
            "content": [
                str(child.id)
                for page in self.pages
                for child in self.children_of(page)
                if child.id in self.content_ids
            ],
        }


def load_form_tree(form: Form) -> None:
    """Prefetch the pages, their children and every condition_option.

    Plain lookup strings rather than Prefetch objects with select_related, so
    a form whose pages were already prefetched by a plainer lookup still gets
    the condition_option level fetched instead of skipped.
    """
    prefetch_related_objects([form], *FORM_TREE_LOOKUPS)


def answers_by_question(form_progress: FormProgress) -> dict[UUID, QuestionAnswer]:
    """The sitting's answers keyed by question id, with selected options loaded.

    Always read fresh: a page submission changes the answers mid-request, and
    the path has to follow them.
    """
    answers = QuestionAnswer.objects.filter(
        form_progress=form_progress
    ).prefetch_related("selected_options")
    return {answer.question_id: answer for answer in answers}


def _condition_holds(
    option: QuestionOption | None, selected: Mapping[UUID, frozenset[UUID]]
) -> bool:
    # `selected` holds only on-path questions, so an unanswered or off-path
    # source makes the condition false.
    return option is None or option.id in selected.get(option.question_id, frozenset())


def _on_path_children(
    page: FormPage, selected: Mapping[UUID, frozenset[UUID]]
) -> list[FormChild]:
    return [
        child
        for child in page.children()
        if _condition_holds(child.condition_option, selected)
    ]


def compute_path(form: Form, answers: Mapping[UUID, QuestionAnswer]) -> SittingPath:
    """The path the given answers produce over the form's current tree."""
    load_form_tree(form)
    option_ids = {
        question_id: frozenset(option.id for option in answer.selected_options.all())
        for question_id, answer in answers.items()
    }
    # Grows as questions prove on-path, so a later gate never reads an
    # answer to a question the sitting was not asked.
    selected: dict[UUID, frozenset[UUID]] = {}
    children_by_page: dict[UUID, tuple[FormChild, ...]] = {}
    all_pages = tuple(form.pages.all())
    for page in all_pages:
        if not _condition_holds(page.condition_option, selected):
            continue
        children = _on_path_children(page, selected)
        if page.children() and not children:
            continue
        children_by_page[page.id] = tuple(children)
        for child in children:
            if isinstance(child, FormQuestion):
                selected[child.id] = option_ids.get(child.id, frozenset())
    return _path(all_pages, children_by_page)


def _path(
    all_pages: tuple[FormPage, ...],
    children_by_page: Mapping[UUID, tuple[FormChild, ...]],
) -> SittingPath:
    """Derive question_ids and content_ids from the children map."""
    children = [child for kids in children_by_page.values() for child in kids]
    return SittingPath(
        all_pages=all_pages,
        children_by_page=children_by_page,
        question_ids=frozenset(c.id for c in children if isinstance(c, FormQuestion)),
        content_ids=frozenset(c.id for c in children if isinstance(c, FormContent)),
    )


def current_path(form_progress: FormProgress) -> SittingPath:
    """The path the sitting's answers give right now."""
    return compute_path(form_progress.form, answers_by_question(form_progress))


def frozen_path(form: Form, asked: Mapping[str, list[str]]) -> SittingPath:
    """The path a completed sitting recorded, rebuilt over the current tree."""
    load_form_tree(form)
    page_ids = {UUID(value) for value in asked["pages"]}
    child_ids = {
        UUID(value) for key in ("questions", "content") for value in asked[key]
    }
    all_pages = tuple(form.pages.all())
    children_by_page = {
        page.id: tuple(c for c in page.children() if c.id in child_ids)
        for page in all_pages
        if page.id in page_ids
    }
    return _path(all_pages, children_by_page)


def full_path(form: Form) -> SittingPath:
    """Every page and child: what a sitting completed before paths were recorded was asked."""
    load_form_tree(form)
    all_pages = tuple(form.pages.all())
    return _path(all_pages, {page.id: tuple(page.children()) for page in all_pages})


def sitting_path(
    form_progress: FormProgress,
    answers: Mapping[UUID, QuestionAnswer] | None = None,
) -> SittingPath:
    """Frozen when the sitting recorded one, everything for an older completed
    sitting, else computed from `answers` (read fresh when not given)."""
    if form_progress.asked is not None:
        return frozen_path(form_progress.form, form_progress.asked)
    if form_progress.completed_time is not None:
        return full_path(form_progress.form)
    if answers is None:
        answers = answers_by_question(form_progress)
    return compute_path(form_progress.form, answers)
