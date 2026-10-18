"""Tests for the attribute rule kind."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
)
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
)
from freedom_ls.registration_rules.kinds import AttributeRuleKind, RuleState
from freedom_ls.registration_rules.models import DATE_BOUND_PAIRS
from freedom_ls.tests.site_context import drop_ambient_request


def _state(rule, **overrides) -> RuleState:
    state = RuleState.from_rule(rule)
    return RuleState(**{**state.__dict__, **overrides})


@pytest.mark.django_db
def test_matches_the_organisations_active_learners_in_pk_order(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    learners = LearnerFactory.create_batch(3, organisation=rule.organisation)
    LearnerFactory(organisation=rule.organisation, is_active=False)
    LearnerFactory(organisation=OrganisationFactory())
    state = RuleState.from_rule(rule)
    drop_ambient_request()

    # Act
    matched = list(AttributeRuleKind().matching_learners(state))

    # Assert
    assert matched == sorted(learners, key=lambda learner: learner.pk)


@pytest.mark.django_db
def test_excludes_another_sites_learners(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    learner = LearnerFactory(organisation=rule.organisation)
    state = RuleState.from_rule(rule)
    drop_ambient_request()

    # Act
    matched = AttributeRuleKind().matching_learners(
        _state(rule, site_id=state.site_id + 1000)
    )

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_matches_nobody_when_the_rule_is_disabled(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=False)
    LearnerFactory(organisation=rule.organisation)
    state = RuleState.from_rule(rule)
    drop_ambient_request()

    # Act
    matched = AttributeRuleKind().matching_learners(state)

    # Assert
    assert not matched.exists()


BOUND = date(2024, 6, 1)

#: Each list condition with the factory that builds its entries and the
#: LearnerHRAttributes field that holds the learner's entry.
LIST_CONDITIONS = [
    pytest.param("job_titles", "job_title", JobTitleFactory, id="job_title"),
    pytest.param("departments", "department", DepartmentFactory, id="department"),
    pytest.param("locations", "location", LocationFactory, id="location"),
]

#: (bound field, stored date field, days from the bound, learner matches).
DATE_CASES = [
    pytest.param(
        bound_field,
        stored,
        offset,
        offset >= 0 if bound_field == on_or_after else offset < 0,
        id=f"{bound_field}-{offset:+d}",
    )
    for on_or_after, before, stored in DATE_BOUND_PAIRS
    for bound_field in (on_or_after, before)
    for offset in (-1, 0, 1)
]


def _matching(rule) -> set:
    state = RuleState.from_rule(rule)
    drop_ambient_request()
    return set(AttributeRuleKind().matching_learners(state))


def _learner_holding(rule, **attributes):
    return LearnerHRAttributesFactory(
        learner__organisation=rule.organisation, **attributes
    ).learner


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "picker",
        "attribute",
        "factory_class",
    ),
    LIST_CONDITIONS,
)
def test_a_learner_holding_a_chosen_entry_matches(
    mock_site_context, picker, attribute, factory_class
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    chosen = factory_class(organisation=rule.organisation)
    AttributeRuleConditionsFactory(rule=rule, **{picker: [chosen]})
    learner = _learner_holding(rule, **{attribute: chosen})

    # Act
    matched = _matching(rule)

    # Assert
    assert learner in matched


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "picker",
        "attribute",
        "factory_class",
    ),
    LIST_CONDITIONS,
)
def test_a_learner_holding_another_entry_does_not_match(
    mock_site_context, picker, attribute, factory_class
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    chosen = factory_class(organisation=rule.organisation)
    AttributeRuleConditionsFactory(rule=rule, **{picker: [chosen]})
    learner = _learner_holding(
        rule, **{attribute: factory_class(organisation=rule.organisation)}
    )

    # Act
    matched = _matching(rule)

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_a_learner_holding_any_one_of_several_chosen_entries_matches(
    mock_site_context,
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    first, second = JobTitleFactory.create_batch(2, organisation=rule.organisation)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[first, second])
    learner = _learner_holding(rule, job_title=second)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner in matched


@pytest.mark.django_db
def test_a_learner_matching_only_one_of_two_lists_does_not_match(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    job_title = JobTitleFactory(organisation=rule.organisation)
    department = DepartmentFactory(organisation=rule.organisation)
    AttributeRuleConditionsFactory(
        rule=rule, job_titles=[job_title], departments=[department]
    )
    learner = _learner_holding(rule, job_title=job_title)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_a_learner_holding_a_chosen_inactive_entry_still_matches(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    retired = JobTitleFactory(organisation=rule.organisation, is_active=False)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[retired])
    learner = _learner_holding(rule, job_title=retired)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner in matched


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "bound_field",
        "stored",
        "offset",
        "expected",
    ),
    DATE_CASES,
)
def test_a_start_date_is_tested_against_its_bound(
    mock_site_context, bound_field, stored, offset, expected
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    AttributeRuleConditionsFactory(rule=rule, **{bound_field: BOUND})
    learner = _learner_holding(rule, **{stored: BOUND + timedelta(days=offset)})

    # Act
    matched = _matching(rule)

    # Assert
    assert (learner in matched) is expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bound_field", [field for pair in DATE_BOUND_PAIRS for field in pair[:2]]
)
def test_a_learner_with_no_date_never_satisfies_a_bound_on_it(
    mock_site_context, bound_field
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    AttributeRuleConditionsFactory(rule=rule, **{bound_field: BOUND})
    learner = _learner_holding(rule)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_a_learner_with_no_attributes_row_never_satisfies_a_list_condition(
    mock_site_context,
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    job_title = JobTitleFactory(organisation=rule.organisation)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[job_title])
    learner = LearnerFactory(organisation=rule.organisation)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_a_learner_with_no_attributes_row_never_satisfies_a_date_condition(
    mock_site_context,
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    AttributeRuleConditionsFactory(rule=rule, organisation_start_on_or_after=BOUND)
    learner = LearnerFactory(organisation=rule.organisation)

    # Act
    matched = _matching(rule)

    # Assert
    assert learner not in matched


@pytest.mark.django_db
def test_an_empty_conditions_row_matches_the_whole_organisation(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    AttributeRuleConditionsFactory(rule=rule)
    learners = LearnerFactory.create_batch(2, organisation=rule.organisation)
    LearnerFactory(organisation=OrganisationFactory())

    # Act
    matched = _matching(rule)

    # Assert
    assert matched == set(learners)
