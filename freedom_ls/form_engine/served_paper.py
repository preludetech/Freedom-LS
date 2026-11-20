"""The paper one quiz sitting is served: its pages, their children and each
question's options, in the order the learner sees them.

Written once per sitting and never changed, so the sitting can be shown and
scored the same way however the form is edited afterwards.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from random import Random
from typing import Protocol
from uuid import UUID

from django.db.models import prefetch_related_objects

from .conditions import SERVED_TREE_LOOKUPS, FormChild, ServedPage, ServedPaper
from .models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)


def new_seed() -> int:
    """The seed a new served paper is shuffled from. Tests patch this, never `random`."""
    return secrets.randbits(63)


def _scope_rng(seed: int, scope: str) -> Random:
    # One private generator per scope, so editing one page or question
    # leaves every other scope's order unchanged for the same seed.
    return Random(f"{seed}:{scope}")  # noqa: S311 - ordering, not security


def shuffle_with_locks[T](
    items: Sequence[T], is_locked: Callable[[T], bool], rng: Random
) -> list[T]:
    """Locked items keep their index; the rest are shuffled into the free positions.

    Shuffling everything and swapping the locked ones back would bias where
    the free items land.
    """
    free_positions = [i for i, item in enumerate(items) if not is_locked(item)]
    free_items = [items[i] for i in free_positions]
    rng.shuffle(free_items)
    result = list(items)
    for position, item in zip(free_positions, free_items, strict=True):
        result[position] = item
    return result


def _served_options(
    question: FormQuestion, form: Form, seed: int
) -> list[QuestionOption]:
    options = list(question.options.all())
    if not form.shuffle_options:
        return options
    return shuffle_with_locks(
        options, lambda o: o.locked, _scope_rng(seed, f"options:{question.id}")
    )


class Groupable(Protocol):
    @property
    def group(self) -> str | None: ...


def shuffle_units[T: Groupable](children: Sequence[T]) -> list[list[T]]:
    """Split a page's children into the lists that move as one when the page shuffles.

    A run of consecutive children sharing a group is one unit, in authored
    order; every other child is a unit of its own. Schema items carry None
    for no group and model rows carry "", so both count as ungrouped.
    """
    units: list[list[T]] = []
    for child in children:
        if child.group and units and units[-1][0].group == child.group:
            units[-1].append(child)
        else:
            units.append([child])
    return units


def _served_children(page: FormPage, form: Form, seed: int) -> list[FormChild]:
    units = shuffle_units(page.children())
    if form.shuffle_questions:
        _scope_rng(seed, f"page:{page.id}").shuffle(units)
    return [child for unit in units for child in unit]


def build_served_paper(form: Form) -> ServedPaper:
    """The paper a sitting starting now is served, shuffled as the form's knobs say."""
    prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)
    seed = new_seed()
    page_rows = list(form.pages.all())
    if form.shuffle_pages:
        _scope_rng(seed, "pages").shuffle(page_rows)
    pages: list[ServedPage] = []
    options: dict[str, list[str]] = {}
    for page in page_rows:
        children = _served_children(page, form, seed)
        pages.append({"id": str(page.id), "children": [str(c.id) for c in children]})
        for child in children:
            if isinstance(child, FormQuestion):
                option_ids = [str(o.id) for o in _served_options(child, form, seed)]
                if option_ids:
                    options[str(child.id)] = option_ids
    # The seed drives the one-time shuffle when the paper is written.
    # `random.shuffle` output is not stable across Python versions, so nothing
    # rebuilds an order from it; the stored lists are the record.
    return {"seed": seed, "pages": pages, "options": options}


def served_child_ids(served_paper: ServedPaper) -> frozenset[UUID]:
    """Every content block and question id the paper serves, on any page."""
    return frozenset(
        UUID(child_id)
        for page in served_paper["pages"]
        for child_id in page["children"]
    )


def ensure_served_paper(form_progress: FormProgress) -> None:
    """Write the sitting's served paper if it is an open quiz sitting without one."""
    if (
        form_progress.served_paper is not None
        or form_progress.completed_time is not None
        or form_progress.form.strategy != FormStrategy.QUIZ
    ):
        return
    # Conditional on the column still being null, then re-read: two requests
    # racing on a sitting's first page both end up holding the first writer's paper.
    FormProgress.objects.filter(pk=form_progress.pk, served_paper__isnull=True).update(
        served_paper=build_served_paper(form_progress.form)
    )
    form_progress.served_paper = FormProgress.objects.values_list(
        "served_paper", flat=True
    ).get(pk=form_progress.pk)
