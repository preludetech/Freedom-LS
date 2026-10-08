"""Resolving a messaging flag through the layers that can set it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from django.db.models import CharField, Expression, F, Value
from django.db.models.functions import Coalesce, NullIf

from freedom_ls.messaging_policy.models import MessagingFlag


class ResolvedFlag(NamedTuple):
    value: str  # MessagingFlag.OPEN or MessagingFlag.CLOSED
    source: str  # the layer that supplied it


# Most specific first. A new layer is one more entry here; nothing else orders them.
LAYER_ORDER: tuple[str, ...] = (
    "learner",
    "registration",
    "cohort",
    "organisation",
    "site",
    "settings",
)


def resolve_flag(layers: Mapping[str, str | None]) -> ResolvedFlag:
    """First layer in LAYER_ORDER whose value is set and not "inherit".

    A layer absent from the mapping, or None (no row), is skipped, so a missing
    row behaves exactly like an all-inherit row. The settings layer is always
    present, so this never falls off the end.
    """
    for layer in LAYER_ORDER:
        value = layers.get(layer)
        if value is not None and value != MessagingFlag.INHERIT:
            return ResolvedFlag(value=value, source=layer)
    raise ValueError("No layer supplied a value; the settings layer is required.")


def resolved_flag_expression(layers: Mapping[str, str | None | F]) -> Expression:
    """The SQL twin of resolve_flag, for layers a row join must supply.

    An F path becomes NullIf(F, "inherit") so a missing row (NULL from the LEFT
    JOIN) and an inherit value both fall through; a constant becomes Value().
    Terms are emitted in LAYER_ORDER and stop at the first constant that is not
    inherit, because nothing below it can win. With no F term left the result is
    that constant itself, so Coalesce (which needs two terms) is only built when a
    join can still change the answer.
    """
    terms: list[Expression] = []
    for layer in LAYER_ORDER:
        value = layers.get(layer)
        if value is None:
            continue
        if isinstance(value, F):
            terms.append(NullIf(value, Value(MessagingFlag.INHERIT.value)))
        elif value != MessagingFlag.INHERIT:
            terms.append(Value(value))
            break
    if not terms:
        raise ValueError("No layer supplied a value; the settings layer is required.")
    if len(terms) == 1:
        return terms[0]
    return Coalesce(*terms, output_field=CharField())
