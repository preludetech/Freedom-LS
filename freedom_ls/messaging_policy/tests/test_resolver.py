from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
)
from freedom_ls.messaging_policy.factories import CohortMessagingConfigFactory
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


# (cohort, organisation, site, settings) -> the layer that wins
CHAIN_TABLE = [
    ("open", "closed", "closed", "closed", ResolvedFlag("open", "cohort")),
    ("closed", "open", "open", "open", ResolvedFlag("closed", "cohort")),
    ("inherit", "open", "closed", "closed", ResolvedFlag("open", "organisation")),
    (None, "closed", "open", "open", ResolvedFlag("closed", "organisation")),
    ("inherit", "inherit", "open", "closed", ResolvedFlag("open", "site")),
    (None, None, "closed", "open", ResolvedFlag("closed", "site")),
    ("inherit", "inherit", "inherit", "open", ResolvedFlag("open", "settings")),
    (None, None, None, "closed", ResolvedFlag("closed", "settings")),
]
CHAIN_IDS = [expected.source + "-" + expected.value for *_, expected in CHAIN_TABLE]


@pytest.mark.parametrize(
    ("cohort", "organisation", "site_value", "settings_value", "expected"),
    CHAIN_TABLE,
    ids=CHAIN_IDS,
)
def test_the_cohort_chain_resolves_the_most_specific_layer(
    cohort: str | None,
    organisation: str | None,
    site_value: str | None,
    settings_value: str,
    expected: ResolvedFlag,
) -> None:
    layers = {
        "cohort": cohort,
        "organisation": organisation,
        "site": site_value,
        "settings": settings_value,
    }

    assert resolve_flag(layers) == expected


def _cohort_with(flag: str | None) -> Cohort:
    """A cohort whose messaging row carries `flag`, or no row for None."""
    if flag is None:
        return cast(Cohort, CohortFactory())
    row = CohortMessagingConfigFactory(learner_to_educator=flag)
    return cast(Cohort, row.cohort)


def _chain_without_cohort(
    organisation: str | None, site_value: str | None, settings_value: str
) -> dict[str, str | None]:
    return {
        "organisation": organisation,
        "site": site_value,
        "settings": settings_value,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cohort", "organisation", "site_value", "settings_value", "expected"),
    CHAIN_TABLE,
    ids=CHAIN_IDS,
)
def test_the_cohort_chain_expression_agrees_with_the_python_resolver(
    mock_site_context: Site,
    cohort: str | None,
    organisation: str | None,
    site_value: str | None,
    settings_value: str,
    expected: ResolvedFlag,
) -> None:
    _cohort_with(cohort)
    expression = resolved_flag_expression(
        {
            **_chain_without_cohort(organisation, site_value, settings_value),
            "cohort": F("messaging_config__learner_to_educator"),
        }
    )

    resolved = (
        Cohort.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == expected.value


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cohort", "organisation", "site_value", "settings_value", "expected"),
    CHAIN_TABLE,
    ids=CHAIN_IDS,
)
def test_the_cohort_registration_chain_expression_agrees_with_the_python_resolver(
    mock_site_context: Site,
    cohort: str | None,
    organisation: str | None,
    site_value: str | None,
    settings_value: str,
    expected: ResolvedFlag,
) -> None:
    CohortCourseRegistrationFactory(cohort=_cohort_with(cohort))
    expression = resolved_flag_expression(
        {
            **_chain_without_cohort(organisation, site_value, settings_value),
            "cohort": F("cohort__messaging_config__learner_to_educator"),
        }
    )

    resolved = (
        CohortCourseRegistration.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == expected.value
