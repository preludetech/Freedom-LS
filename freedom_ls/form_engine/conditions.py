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
from typing import TypedDict, cast
from uuid import UUID

from django.db.models import prefetch_related_objects

from .live_tree import live_children
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

# The tree plus each question's options: what a served paper orders, and what
# a computed path hands out.
SERVED_TREE_LOOKUPS = (*FORM_TREE_LOOKUPS, "pages__questions__options")


class ServedPage(TypedDict):
    id: str
    children: list[str]


class ServedPaper(TypedDict):
    """The stored shape of `FormProgress.served_paper`. Every id is a string uuid."""

    seed: int
    pages: list[ServedPage]
    options: dict[str, list[str]]


@dataclass(frozen=True, eq=False)
class SittingPath:
    """The pages, questions and content blocks one sitting is asked, in the order it is asked them.

    Page numbers are authored indexes (the URL's numbers); positions are places
    among the on-path pages (what the learner reads). The two only coincide
    when nothing is skipped and the pages are asked in authored order.
    """

    all_pages: tuple[FormPage, ...]
    # On-path page id -> its on-path children, in page order.
    children_by_page: Mapping[UUID, tuple[FormChild, ...]]
    question_ids: frozenset[UUID]
    content_ids: frozenset[UUID]
    # Option order per question; None when every option the question has is shown,
    # as for a path built over the whole form.
    served_options_by_question: Mapping[UUID, tuple[QuestionOption, ...]] | None = None
    # True when the served paper names a page, child or option the form lacks.
    has_missing_served_items: bool = False
    _numbered: tuple[tuple[int, FormPage], ...] = field(init=False, repr=False)
    _page_positions: dict[int, int] = field(init=False, repr=False)
    _question_positions: dict[UUID, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        authored = {
            page.id: (number, page)
            for number, page in enumerate(self.all_pages, start=1)
        }
        numbered = tuple(authored[page_id] for page_id in self.children_by_page)
        object.__setattr__(self, "_numbered", numbered)
        object.__setattr__(
            self,
            "_page_positions",
            {number: position for position, (number, _) in enumerate(numbered, 1)},
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
        """(authored number, page) for each on-path page, in the order the sitting meets them."""
        return list(self._numbered)

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

    def page_number_of(self, page_id: UUID | None) -> int | None:
        """The authored number of one of the form's pages, on the path or off it."""
        return next(
            (
                number
                for number, page in enumerate(self.all_pages, start=1)
                if page.id == page_id
            ),
            None,
        )

    def page_position(self, number: int) -> int:
        """The 1-based place of an on-path page among the on-path pages."""
        return self._page_positions[number]

    def question_positions(self) -> dict[UUID, int]:
        """The 1-based place of each on-path question among the on-path questions."""
        return self._question_positions

    def _number_at(self, position: int) -> int | None:
        """The authored number of the page at this position, or None when there is none."""
        if not 1 <= position <= len(self._numbered):
            return None
        return self._numbered[position - 1][0]

    def _first_number_above(self, number: int) -> int | None:
        """The first page, in path order, whose authored number is greater than `number`."""
        return next((n for n in self._page_positions if n > number), None)

    def next_page_number(self, after: int) -> int | None:
        if after in self._page_positions:
            return self._number_at(self._page_positions[after] + 1)
        return self._first_number_above(after)

    def previous_page_number(self, before: int) -> int | None:
        if before in self._page_positions:
            return self._number_at(self._page_positions[before] - 1)
        return next((n for n in reversed(self._page_positions) if n < before), None)

    def first_page_number_at_or_after(self, number: int) -> int | None:
        if number in self._page_positions:
            return number
        return self._first_number_above(number)

    def reached_position(self, number: int) -> int:
        """How far along the path a sitting that reached authored page `number` has got.

        A number off the path counts as every page before the one it would land
        on, so a reached page the answers have since taken off the path still
        compares.
        """
        if number in self._page_positions:
            return self._page_positions[number]
        landing = self._first_number_above(number)
        return self.page_count if landing is None else self._page_positions[landing] - 1

    def options_of(self, question: FormQuestion) -> list[QuestionOption]:
        """The question's options in the order this sitting is served them."""
        if self.served_options_by_question is None:
            return list(question.options.all())
        return list(self.served_options_by_question.get(question.id, ()))

    def options_added_since(self, question: FormQuestion) -> list[QuestionOption]:
        """The question's current options this sitting was not served, in
        authored order: options added after it was served, retired ones left
        out. Empty for a path with no served paper, where every current option
        is already served.

        A reviewer needs them because marking reads the current options; a
        sitting being answered must never be offered them.
        """
        served = {option.id for option in self.options_of(question)}
        return [
            option
            for option in question.options.all()
            if option.id not in served and not option.is_retired
        ]

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


def _kept_children(
    page: FormPage, answers: Mapping[UUID, QuestionAnswer]
) -> list[FormChild]:
    """The page's children a sitting with no served paper may be shown.

    The live children of a live page, plus any question the sitting has already
    answered: one retired since, or one on a page retired since. Its answer is
    kept, so the question stays where the sitting can see it.
    """
    live = [] if page.is_retired else live_children(page)
    return [
        child
        for child in page.children()
        if child in live or (isinstance(child, FormQuestion) and child.id in answers)
    ]


def _on_path_children(
    page: FormPage,
    selected: Mapping[UUID, frozenset[UUID]],
    answers: Mapping[UUID, QuestionAnswer],
) -> list[FormChild]:
    return [
        child
        for child in _kept_children(page, answers)
        if _condition_holds(child.condition_option, selected)
    ]


def compute_path(form: Form, answers: Mapping[UUID, QuestionAnswer]) -> SittingPath:
    """The path the given answers produce over the form's live tree.

    Its options are the live ones, so a sitting not yet served a paper is offered
    no retired option. A question the sitting has already answered stays on the
    path after it is retired, with any retired option the answer selected, so
    finishing the sitting keeps the answer. A retired question opens no gate.
    """
    prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)
    option_ids = {
        question_id: frozenset(option.id for option in answer.selected_options.all())
        for question_id, answer in answers.items()
    }
    # Grows as questions prove on-path, so a later gate never reads an
    # answer to a question the sitting was not asked.
    selected: dict[UUID, frozenset[UUID]] = {}
    children_by_page: dict[UUID, tuple[FormChild, ...]] = {}
    options_by_question: dict[UUID, tuple[QuestionOption, ...]] = {}
    all_pages = tuple(
        page
        for page in form.pages.all()
        if not page.is_retired or _kept_children(page, answers)
    )
    for page in all_pages:
        if not _condition_holds(page.condition_option, selected):
            continue
        children = _on_path_children(page, selected, answers)
        # A page authored with children is left off the path once none of them
        # remain on it, whether gated out or retired. Only a page authored with
        # no children at all is kept as an empty page.
        if page.children() and not children:
            continue
        children_by_page[page.id] = tuple(children)
        for child in children:
            if isinstance(child, FormQuestion):
                chosen = option_ids.get(child.id, frozenset())
                if not (child.is_retired or page.is_retired):
                    selected[child.id] = chosen
                options_by_question[child.id] = tuple(
                    option
                    for option in child.options.all()
                    if not option.is_retired or option.id in chosen
                )
    return _path(all_pages, children_by_page, options_by_question)


def _path(
    all_pages: tuple[FormPage, ...],
    children_by_page: Mapping[UUID, tuple[FormChild, ...]],
    served_options_by_question: Mapping[UUID, tuple[QuestionOption, ...]] | None = None,
    has_missing_served_items: bool = False,
) -> SittingPath:
    """Derive question_ids and content_ids from the children map."""
    children = [child for kids in children_by_page.values() for child in kids]
    return SittingPath(
        all_pages=all_pages,
        children_by_page=children_by_page,
        question_ids=frozenset(c.id for c in children if isinstance(c, FormQuestion)),
        content_ids=frozenset(c.id for c in children if isinstance(c, FormContent)),
        served_options_by_question=served_options_by_question,
        has_missing_served_items=has_missing_served_items,
    )


def served_path(form: Form, served_paper: ServedPaper) -> SittingPath:
    """The path a served paper records, rebuilt over the form's current tree.

    An item missing from the form is skipped, whether it was deleted or
    moved to another form. A question moved to another page of this form is
    still shown under the page it was served on. A question none of whose
    served options remain, or that was served with none, shows the options it
    currently has.
    """
    prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)
    all_pages = tuple(form.pages.all())
    pages_by_id = {str(page.id): page for page in all_pages}
    children_by_id = {str(c.id): c for page in all_pages for c in page.children()}
    served_option_ids = served_paper["options"]
    missing = False
    children_by_page: dict[UUID, tuple[FormChild, ...]] = {}
    served_options_by_question: dict[UUID, tuple[QuestionOption, ...]] = {}
    for served_page in served_paper["pages"]:
        page = pages_by_id.get(served_page["id"])
        if page is None:
            missing = True
            continue
        children = tuple(
            children_by_id[i] for i in served_page["children"] if i in children_by_id
        )
        missing = missing or len(children) != len(served_page["children"])
        # A page that was empty when served is kept, as compute_path keeps it;
        # one whose children have all gone has nothing left to show.
        if served_page["children"] and not children:
            continue
        children_by_page[page.id] = children
        for child in children:
            if not isinstance(child, FormQuestion):
                continue
            current = {str(option.id): option for option in child.options.all()}
            served_ids = served_option_ids.get(str(child.id), [])
            options = tuple(current[i] for i in served_ids if i in current)
            missing = missing or len(options) != len(served_ids)
            # With none of its served options left, the question would offer
            # nothing to choose, so it falls back to the options it has.
            served_options_by_question[child.id] = options or tuple(current.values())
    return _path(all_pages, children_by_page, served_options_by_question, missing)


def current_path(form_progress: FormProgress) -> SittingPath:
    """The sitting's served paper when it has one, else the path its answers give right now."""
    if form_progress.served_paper is not None:
        return served_path(
            form_progress.form, cast("ServedPaper", form_progress.served_paper)
        )
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
    """The served paper when the sitting has one, whatever the form's strategy is
    now; else frozen when the sitting recorded one, everything for an older
    completed sitting, else computed from `answers` (read fresh when not given)."""
    if form_progress.served_paper is not None:
        return served_path(
            form_progress.form, cast("ServedPaper", form_progress.served_paper)
        )
    if form_progress.asked is not None:
        return frozen_path(form_progress.form, form_progress.asked)
    if form_progress.completed_time is not None:
        return full_path(form_progress.form)
    if answers is None:
        answers = answers_by_question(form_progress)
    return compute_path(form_progress.form, answers)
