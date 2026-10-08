from __future__ import annotations

from typing import cast

import pytest

from django.contrib.sites.models import Site
from django.db.models import CharField, F, Value
from django.db.models.functions import Coalesce

from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.messaging_policy.factories import (
    CohortCourseRegistrationMessagingConfigFactory,
    CohortMessagingConfigFactory,
    LearnerCourseRegistrationMessagingConfigFactory,
    LearnerMessagingConfigFactory,
)
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


# The layers each kind of candidate passes through, most specific first.
CHAINS = {
    "educator": ("learner", "organisation", "site", "settings"),
    "cohort": ("learner", "cohort", "organisation", "site", "settings"),
    "individual_registration": (
        "learner",
        "registration",
        "organisation",
        "site",
        "settings",
    ),
    "cohort_registration": (
        "learner",
        "registration",
        "cohort",
        "organisation",
        "site",
        "settings",
    ),
}


@pytest.mark.parametrize("chain", CHAINS)
@pytest.mark.parametrize(
    ("value", "opposite"), [("open", "closed"), ("closed", "open")]
)
def test_a_learner_layer_beats_every_lower_layer_set_to_the_opposite(
    chain: str, value: str, opposite: str
) -> None:
    layers = dict.fromkeys(CHAINS[chain], opposite)
    layers["learner"] = value

    assert resolve_flag(layers) == ResolvedFlag(value, "learner")


@pytest.mark.parametrize("chain", ["individual_registration", "cohort_registration"])
def test_a_registration_layer_beats_the_layers_below_it(chain: str) -> None:
    layers = dict.fromkeys(CHAINS[chain], "closed")
    layers.update({"learner": "inherit", "registration": "open"})

    assert resolve_flag(layers) == ResolvedFlag("open", "registration")


@pytest.mark.parametrize(
    ("registration", "cohort", "organisation", "expected"),
    [
        ("open", "closed", "closed", ResolvedFlag("open", "registration")),
        ("closed", "open", "open", ResolvedFlag("closed", "registration")),
        ("inherit", "open", "closed", ResolvedFlag("open", "cohort")),
        (None, "closed", "open", ResolvedFlag("closed", "cohort")),
        ("inherit", "inherit", "closed", ResolvedFlag("closed", "organisation")),
        (None, None, "open", ResolvedFlag("open", "organisation")),
    ],
)
def test_a_cohort_registration_chain_resolves_registration_then_cohort_then_organisation(
    registration: str | None,
    cohort: str | None,
    organisation: str,
    expected: ResolvedFlag,
) -> None:
    layers = {
        "learner": None,
        "registration": registration,
        "cohort": cohort,
        "organisation": organisation,
        "settings": "open" if organisation == "closed" else "closed",
    }

    assert resolve_flag(layers) == expected


# (leaf, organisation, site, settings) -> the resolved value
LEAF_TABLE = [
    ("open", "closed", "closed", "closed", "open"),
    ("closed", "open", "open", "open", "closed"),
    ("inherit", "open", "closed", "closed", "open"),
    (None, "closed", "open", "open", "closed"),
    ("inherit", "inherit", "open", "closed", "open"),
    (None, None, None, "closed", "closed"),
]


def _learner_with(flag: str | None) -> Learner:
    """A learner whose messaging row carries `flag`, or no row for None."""
    if flag is None:
        return cast(Learner, LearnerFactory())
    return cast(
        Learner, LearnerMessagingConfigFactory(learner_to_educator=flag).learner
    )


def _individual_registration_with(flag: str | None) -> LearnerCourseRegistration:
    """A registration whose messaging row carries `flag`, or no row for None."""
    if flag is None:
        return cast(LearnerCourseRegistration, LearnerCourseRegistrationFactory())
    row = LearnerCourseRegistrationMessagingConfigFactory(learner_to_course_peer=flag)
    return cast(LearnerCourseRegistration, row.registration)


def _cohort_registration_with(
    flag: str | None, cohort: Cohort
) -> CohortCourseRegistration:
    """A registration of `cohort` whose messaging row carries `flag`, or no row for None."""
    registration = cast(
        CohortCourseRegistration, CohortCourseRegistrationFactory(cohort=cohort)
    )
    if flag is not None:
        CohortCourseRegistrationMessagingConfigFactory(
            registration=registration, learner_to_course_peer=flag
        )
    return registration


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("leaf", "organisation", "site_value", "settings_value", "expected"), LEAF_TABLE
)
def test_the_learner_chain_expression_agrees_with_the_python_resolver(
    mock_site_context: Site,
    leaf: str | None,
    organisation: str | None,
    site_value: str | None,
    settings_value: str,
    expected: str,
) -> None:
    _learner_with(leaf)
    expression = resolved_flag_expression(
        {
            "learner": F("messaging_config__learner_to_educator"),
            "organisation": organisation,
            "site": site_value,
            "settings": settings_value,
        }
    )

    resolved = (
        Learner.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("leaf", "organisation", "site_value", "settings_value", "expected"), LEAF_TABLE
)
def test_the_individual_registration_chain_expression_agrees_with_the_python_resolver(
    mock_site_context: Site,
    leaf: str | None,
    organisation: str | None,
    site_value: str | None,
    settings_value: str,
    expected: str,
) -> None:
    _individual_registration_with(leaf)
    expression = resolved_flag_expression(
        {
            "registration": F("messaging_config__learner_to_course_peer"),
            "organisation": organisation,
            "site": site_value,
            "settings": settings_value,
        }
    )

    resolved = (
        LearnerCourseRegistration.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == expected


# (registration, cohort, organisation, settings) -> the resolved value
REGISTRATION_OVER_COHORT_TABLE = [
    ("open", "closed", "closed", "closed", "open"),
    ("closed", "open", "open", "open", "closed"),
    ("inherit", "open", "closed", "closed", "open"),
    (None, "closed", "open", "open", "closed"),
    ("inherit", "inherit", "closed", "open", "closed"),
    (None, None, None, "open", "open"),
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("registration", "cohort", "organisation", "settings_value", "expected"),
    REGISTRATION_OVER_COHORT_TABLE,
)
def test_the_cohort_registration_chain_expression_resolves_registration_then_cohort(
    mock_site_context: Site,
    registration: str | None,
    cohort: str | None,
    organisation: str | None,
    settings_value: str,
    expected: str,
) -> None:
    _cohort_registration_with(registration, _cohort_with(cohort))
    expression = resolved_flag_expression(
        {
            "registration": F("messaging_config__learner_to_course_peer"),
            "cohort": F("cohort__messaging_config__learner_to_educator"),
            "organisation": organisation,
            "settings": settings_value,
        }
    )

    resolved = (
        CohortCourseRegistration.objects.annotate(resolved=expression)
        .values_list("resolved", flat=True)
        .get()
    )

    assert resolved == expected
