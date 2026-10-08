from __future__ import annotations

import pytest

from django.contrib.sites.models import Site
from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import Learner
from freedom_ls.messaging_policy.resolver import (
    ResolvedFlag,
    resolve_flag,
    resolved_flag_expression,
)


def test_the_settings_layer_alone_decides() -> None:
    assert resolve_flag({"settings": "closed"}) == ResolvedFlag("closed", "settings")


def test_a_none_layer_is_skipped() -> None:
    assert resolve_flag({"cohort": None, "settings": "open"}) == ResolvedFlag(
        "open", "settings"
    )


def test_an_inherit_layer_is_skipped() -> None:
    assert resolve_flag({"site": "inherit", "settings": "open"}) == ResolvedFlag(
        "open", "settings"
    )


def test_the_most_specific_set_layer_wins() -> None:
    layers = {"cohort": "open", "site": "closed", "settings": "closed"}

    assert resolve_flag(layers) == ResolvedFlag("open", "cohort")


def test_a_constant_only_expression_is_a_value() -> None:
    expression = resolved_flag_expression({"settings": "closed"})

    assert isinstance(expression, Value)
    assert expression.value == "closed"


def test_a_constant_above_the_settings_layer_cuts_the_expression_short() -> None:
    expression = resolved_flag_expression({"site": "open", "settings": "closed"})

    assert isinstance(expression, Value)
    assert expression.value == "open"


@pytest.mark.parametrize(
    ("site", "settings_value", "expected"),
    [
        (None, "open", ResolvedFlag("open", "settings")),
        ("inherit", "closed", ResolvedFlag("closed", "settings")),
        ("open", "closed", ResolvedFlag("open", "site")),
        ("closed", "open", ResolvedFlag("closed", "site")),
    ],
)
def test_the_site_layer_over_the_settings_layer(
    site: str | None, settings_value: str, expected: ResolvedFlag
) -> None:
    assert resolve_flag({"site": site, "settings": settings_value}) == expected


@pytest.mark.django_db
def test_a_joined_layer_over_a_constant_falls_back_to_the_constant(
    mock_site_context: Site,
) -> None:
    LearnerFactory()
    expression = resolved_flag_expression(
        {"cohort": F("cohortmembership__cohort__name"), "settings": "closed"}
    )

    assert isinstance(expression, Coalesce)
    resolved = (
        Learner.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )
    assert resolved == "closed"


@pytest.mark.django_db
def test_an_inherit_value_in_a_joined_layer_falls_through(
    mock_site_context: Site,
) -> None:
    LearnerFactory(organisation__name="inherit")
    expression = resolved_flag_expression(
        {"organisation": F("organisation__name"), "settings": "open"}
    )

    resolved = (
        Learner.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == "open"
    assert expression.output_field.__class__ is CharField
