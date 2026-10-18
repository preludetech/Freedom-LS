"""Tests for the attribute rule kind."""

from __future__ import annotations

import pytest

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.factories import RegistrationRuleFactory
from freedom_ls.registration_rules.kinds import AttributeRuleKind, RuleState
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
