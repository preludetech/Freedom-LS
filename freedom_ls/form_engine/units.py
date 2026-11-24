"""How a page's children split into the units that shuffle and draw as one.

Kept free of model imports so the models, the served paper and the content
validator can all share the one rule.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol


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


def unit_question_counts[T](
    units: Sequence[Sequence[T]], is_question: Callable[[T], bool]
) -> list[int]:
    """How many questions each unit holds.

    Takes a predicate because schema items and model rows are told apart by
    different question classes.
    """
    return [sum(is_question(child) for child in unit) for unit in units]
