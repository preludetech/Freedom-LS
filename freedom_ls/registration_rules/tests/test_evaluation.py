"""Tests for evaluating a registration rule."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.contrib.sites.models import Site
from django.db.models.signals import post_save

from freedom_ls.comms.models import Notification
from freedom_ls.hr_attributes.factories import OrganisationHRSettingsFactory
from freedom_ls.hr_attributes.models import OrganisationHRSettings
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.webhooks.models import WebhookEvent

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.evaluation import evaluate_rule
from freedom_ls.registration_rules.factories import (
    RegistrationRuleFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration
from freedom_ls.tests.site_context import drop_ambient_request


def _enabled_rule(**overrides):
    rule = RegistrationRuleFactory(is_enabled=True, **overrides)
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=True
    )
    return rule


def _registrations_for(rule):
    return LearnerCourseRegistration._base_manager.filter(course=rule.course)


@pytest.mark.django_db
def test_registers_a_matching_learner_and_records_the_rule(
    mock_site_context, django_capture_on_commit_callbacks
):
    # Arrange
    rule = _enabled_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    registration = _registrations_for(rule).get(learner=learner)
    assert result.registered == (learner.pk,)
    assert registration.is_active is True
    assert registration.self_registered is False
    link = RuleRegistration._base_manager.get(registration=registration)
    assert link.rule == rule
    assert link.rule_name == rule.name
    assert link.is_retracted is False
    assert CourseProgress._base_manager.filter(
        learner=learner, course=rule.course
    ).exists()
    assert (
        Notification._base_manager.filter(
            user=learner.user, category="course.registered"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_a_finished_run_stamps_last_evaluated_at_without_moving_updated_at(
    mock_site_context,
):
    # Arrange
    with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
        rule = _enabled_rule()
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    updated_at = RegistrationRule._base_manager.get(pk=rule.pk).updated_at

    # Act
    with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
        evaluate_rule(rule.pk, rule.site_id)

    # Assert
    rule = RegistrationRule._base_manager.get(pk=rule.pk)
    assert rule.last_evaluated_at == datetime(2026, 2, 1, tzinfo=UTC)
    assert rule.updated_at == updated_at


@pytest.mark.django_db
@pytest.mark.parametrize("settings_row", [False, True], ids=["switch-off", "no-row"])
def test_registers_nobody_while_the_organisation_switch_is_off(
    mock_site_context, settings_row
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    if settings_row:
        OrganisationHRSettings._base_manager.filter(
            organisation=rule.organisation
        ).delete()
    else:
        OrganisationHRSettingsFactory(
            organisation=rule.organisation, registration_rules_enabled=False
        )
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not _registrations_for(rule).exists()
    rule = RegistrationRule._base_manager.get(pk=rule.pk)
    assert rule.last_evaluated_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "registration_state",
    [
        {"is_active": True, "self_registered": False},
        {"is_active": False, "self_registered": False},
        {"is_active": True, "self_registered": True},
        {"is_active": False, "self_registered": True},
    ],
)
def test_never_touches_a_registration_somebody_else_made(
    mock_site_context, registration_state
):
    # Arrange
    rule = _enabled_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    existing = LearnerCourseRegistrationFactory(
        learner=learner, course=rule.course, **registration_state
    )
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    existing.refresh_from_db()
    assert result.registered == ()
    assert existing.is_active is registration_state["is_active"]
    assert existing.self_registered is registration_state["self_registered"]
    assert not RuleRegistration._base_manager.filter(registration=existing).exists()


@pytest.mark.django_db
def test_registers_every_learner_across_several_batches(mock_site_context, settings):
    # Arrange
    settings.REGISTRATION_RULE_BATCH_SIZE = 2
    rule = _enabled_rule()
    learners = LearnerFactory.create_batch(5, organisation=rule.organisation)
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert set(result.registered) == {learner.pk for learner in learners}
    assert _registrations_for(rule).count() == 5


def _on_first_registration_saved(action):
    """Connect `action` to the first LearnerCourseRegistration save; returns a disconnect."""
    calls: list[int] = []

    def receiver(sender, instance, created, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            action()

    post_save.connect(receiver, sender=LearnerCourseRegistration, weak=False)
    return lambda: post_save.disconnect(receiver, sender=LearnerCourseRegistration)


@pytest.mark.django_db
def test_a_rule_disabled_between_batches_registers_nobody_afterwards(
    mock_site_context, settings
):
    # Arrange
    settings.REGISTRATION_RULE_BATCH_SIZE = 2
    rule = _enabled_rule()
    LearnerFactory.create_batch(5, organisation=rule.organisation)
    drop_ambient_request()
    disconnect = _on_first_registration_saved(
        lambda: RegistrationRule._base_manager.filter(pk=rule.pk).update(
            is_enabled=False
        )
    )

    # Act
    try:
        evaluate_rule(rule.pk, rule.site_id)
    finally:
        disconnect()

    # Assert
    assert _registrations_for(rule).count() == 2


@pytest.mark.django_db
def test_a_switch_turned_off_between_batches_stops_the_run(mock_site_context, settings):
    # Arrange
    settings.REGISTRATION_RULE_BATCH_SIZE = 2
    rule = _enabled_rule()
    LearnerFactory.create_batch(5, organisation=rule.organisation)
    drop_ambient_request()
    disconnect = _on_first_registration_saved(
        lambda: OrganisationHRSettings._base_manager.filter(
            organisation=rule.organisation
        ).update(registration_rules_enabled=False)
    )

    # Act
    try:
        evaluate_rule(rule.pk, rule.site_id)
    finally:
        disconnect()

    # Assert
    assert _registrations_for(rule).count() == 2
    rule = RegistrationRule._base_manager.get(pk=rule.pk)
    assert rule.last_evaluated_at is None


@pytest.mark.django_db
def test_leaves_learners_of_the_same_organisation_on_another_site_alone(
    mock_site_context,
):
    # Arrange
    rule = _enabled_rule()
    own = LearnerFactory(organisation=rule.organisation)
    other_site = Site.objects.create(domain="other.example.com", name="Other")
    foreign = Learner._base_manager.create(
        site=other_site,
        user=LearnerFactory().user,
        organisation=rule.organisation,
    )
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    registered = set(_registrations_for(rule).values_list("learner_id", flat=True))
    assert registered == {own.pk}
    assert foreign.pk not in registered


@pytest.mark.django_db
def test_a_run_against_another_site_does_nothing(mock_site_context):
    # Arrange
    rule = _enabled_rule()
    LearnerFactory(organisation=rule.organisation)
    other_site = Site.objects.create(domain="other.example.com", name="Other")
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, other_site.pk)

    # Assert
    assert result.registered == ()
    assert not _registrations_for(rule).exists()


@pytest.mark.django_db
def test_a_learner_the_rule_already_registered_gets_no_second_row(mock_site_context):
    # Arrange
    rule = _enabled_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    RuleRegistrationFactory(
        rule=rule,
        registration=LearnerCourseRegistrationFactory(
            learner=learner, course=rule.course, self_registered=False
        ),
    )
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result.registered == ()
    assert _registrations_for(rule).count() == 1
    assert RuleRegistration._base_manager.filter(rule=rule).count() == 1


@pytest.mark.django_db
def test_a_rule_made_registration_fires_the_webhook_with_no_request(
    mock_site_context, settings, django_capture_on_commit_callbacks
):
    # Arrange
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    rule = _enabled_rule()
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_rule(rule.pk, rule.site_id)

    # Assert
    event = WebhookEvent._base_manager.get(event_type="course.registered")
    assert event.site_id == rule.site_id
    assert event.payload["course_id"] == str(rule.course_id)
