"""The paper one quiz sitting is served: its pages, their children and each
question's options, in the order the learner sees them.

Written once per sitting and never changed, so the sitting can be shown and
scored the same way however the form is edited afterwards.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from random import Random
from uuid import UUID

from django.db.models import prefetch_related_objects

from .conditions import SERVED_TREE_LOOKUPS, FormChild, ServedPage, ServedPaper
from .live_tree import live_children, live_options, live_pages
from .models import (
    Form,
    FormPage,
    FormProgress,
    FormQuestion,
    FormStrategy,
    QuestionOption,
)
from .units import shuffle_units


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
    options = live_options(question)
    if not form.shuffle_options:
        return options
    return shuffle_with_locks(
        options, lambda o: o.locked, _scope_rng(seed, f"options:{question.id}")
    )


def _drawn_units[T](units: list[T], page: FormPage, seed: int) -> list[T]:
    """The units a sitting is served from the page, in authored order.

    The draw has its own generator, so turning a shuffle knob on or off, or
    editing another page, leaves the drawn set unchanged for the same seed.
    Sorting the picked indices keeps authored order; the page shuffle, when
    it is on, reorders afterwards. A draw above the unit count serves every
    unit rather than refusing the sitting.
    """
    if page.draw is None:
        return units
    rng = _scope_rng(seed, f"draw:{page.id}")
    picked = sorted(rng.sample(range(len(units)), min(page.draw, len(units))))
    return [units[index] for index in picked]


def _served_children(page: FormPage, form: Form, seed: int) -> list[FormChild]:
    units = _drawn_units(shuffle_units(live_children(page)), page, seed)
    if form.shuffle_questions:
        _scope_rng(seed, f"page:{page.id}").shuffle(units)
    return [child for unit in units for child in unit]


def build_served_paper(form: Form) -> ServedPaper:
    """The paper a sitting starting now is served, shuffled as the form's knobs say."""
    prefetch_related_objects([form], *SERVED_TREE_LOOKUPS)
    seed = new_seed()
    # A page authored with children is left off once all of them are retired,
    # as compute_path leaves it off; a page authored empty is still served.
    page_rows = [
        page for page in live_pages(form) if not page.children() or live_children(page)
    ]
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
    # The seed drives the one-time draw and shuffle when the paper is written.
    # `random.sample` and `random.shuffle` output is not stable across Python
    # versions, so nothing rebuilds a paper from it; the stored lists are the record.
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
