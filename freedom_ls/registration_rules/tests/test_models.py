"""Tests for the registration rule models."""

from __future__ import annotations

from datetime import date

import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseAudience
from freedom_ls.learner_management.queries import COURSE_NOT_OPEN_MESSAGE
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRecommendationFactory,
)
from freedom_ls.registration_rules.models import DATE_BOUND_PAIRS, RuleRecommendation

LOWER = date(2024, 6, 1)

#: (on-or-after field, before field), one per start date.
PAIRS = [pytest.param(pair[0], pair[1], id=pair[2]) for pair in DATE_BOUND_PAIRS]


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "on_or_after",
        "before",
    ),
    PAIRS,
)
def test_a_before_date_earlier_than_its_on_or_after_date_is_refused_on_the_before_field(
    mock_site_context, on_or_after, before
):
    # Arrange
    conditions = AttributeRuleConditionsFactory.build(
        **{on_or_after: LOWER, before: date(2024, 1, 1)}
    )

    # Act
    with pytest.raises(ValidationError) as excinfo:
        conditions.clean()

    # Assert
    assert set(excinfo.value.error_dict) == {before}


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "on_or_after",
        "before",
    ),
    PAIRS,
)
def test_equal_dates_are_refused(mock_site_context, on_or_after, before):
    # Arrange
    conditions = AttributeRuleConditionsFactory.build(
        **{on_or_after: LOWER, before: LOWER}
    )

    # Act
    with pytest.raises(ValidationError) as excinfo:
        conditions.clean()

    # Assert
    assert set(excinfo.value.error_dict) == {before}


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "on_or_after",
        "before",
    ),
    PAIRS,
)
def test_a_before_date_later_than_its_on_or_after_date_is_accepted(
    mock_site_context, on_or_after, before
):
    # Arrange
    conditions = AttributeRuleConditionsFactory.build(
        **{on_or_after: LOWER, before: date(2025, 1, 1)}
    )

    # Act / Assert
    conditions.clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "field", [field for pair in DATE_BOUND_PAIRS for field in pair[:2]]
)
def test_one_bound_alone_is_accepted(mock_site_context, field):
    # Arrange
    conditions = AttributeRuleConditionsFactory.build(**{field: LOWER})

    # Act / Assert
    conditions.clean()


@pytest.mark.django_db
def test_a_rule_cannot_recommend_the_same_recommendation_twice(mock_site_context):
    # Arrange
    existing = RuleRecommendationFactory()

    # Act / Assert
    with pytest.raises(IntegrityError), transaction.atomic():
        RuleRecommendation.objects.create(
            recommendation=existing.recommendation, rule=existing.rule
        )


@pytest.mark.django_db
def test_a_rule_for_a_course_closed_to_its_organisation_is_refused(mock_site_context):
    course = CourseFactory(audience=CourseAudience.ORGANISATION_LEARNERS)
    course.organisations.add(OrganisationFactory())
    rule = RegistrationRuleFactory.build(
        course=course, organisation=OrganisationFactory()
    )

    with pytest.raises(ValidationError) as error:
        rule.full_clean(exclude=["site"])

    assert COURSE_NOT_OPEN_MESSAGE in error.value.message_dict["course"]


@pytest.mark.django_db
def test_a_rule_for_a_course_open_to_its_organisation_is_accepted(mock_site_context):
    organisation = OrganisationFactory()
    course = CourseFactory(audience=CourseAudience.ORGANISATION_LEARNERS)
    course.organisations.add(organisation)
    rule = RegistrationRuleFactory.build(course=course, organisation=organisation)

    rule.full_clean(exclude=["site"])
