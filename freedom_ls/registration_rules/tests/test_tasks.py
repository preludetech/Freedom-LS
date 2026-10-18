"""Tests for the registration rule tasks."""

from __future__ import annotations

import pytest

from freedom_ls.hr_attributes.factories import OrganisationHRSettingsFactory
from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.factories import RegistrationRuleFactory
from freedom_ls.registration_rules.tasks import evaluate_rule_task
from freedom_ls.tests.site_context import drop_ambient_request


@pytest.mark.django_db
def test_evaluate_rule_task_takes_the_ids_a_queue_carries(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=True
    )
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_rule_task.func(str(rule.pk), rule.site_id)

    # Assert
    assert LearnerCourseRegistration._base_manager.filter(
        learner=learner, course=rule.course
    ).exists()
