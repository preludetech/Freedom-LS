"""Tests for evaluating a registration rule."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.db.models.signals import post_save

from freedom_ls.accounts.factories import SiteFactory
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


@pytest.fixture
def rule_run_for_one_learner(mock_site_context, django_capture_on_commit_callbacks):
    rule = _enabled_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    with django_capture_on_commit_callbacks(execute=True):
        result = evaluate_rule(rule.pk, rule.site_id)
    return rule, learner, result


@pytest.mark.django_db
def test_registers_a_matching_learner_and_links_the_rule(rule_run_for_one_learner):
    # Arrange
    rule, learner, _ = rule_run_for_one_learner

    # Act
    registration = _registrations_for(rule).get(learner=learner)
    link = RuleRegistration._base_manager.get(registration=registration)

    # Assert
    assert registration.is_active is True
    assert registration.self_registered is False
    assert link.rule == rule
    assert link.rule_name == rule.name
    assert link.is_retracted is False


@pytest.mark.django_db
def test_the_run_reports_the_learner_it_registered(rule_run_for_one_learner):
    # Arrange
    _, learner, result = rule_run_for_one_learner

    # Assert
    assert result.registered == (learner.pk,)


@pytest.mark.django_db
def test_registering_a_matching_learner_creates_their_course_progress(
    rule_run_for_one_learner,
):
    # Arrange
    rule, learner, _ = rule_run_for_one_learner

    # Assert
    assert CourseProgress._base_manager.filter(
        learner=learner, course=rule.course
    ).exists()


@pytest.mark.django_db
def test_registering_a_matching_learner_raises_one_course_registered_notification(
    rule_run_for_one_learner,
):
    # Arrange
    _, learner, _ = rule_run_for_one_learner

    # Assert
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


def _assert_nothing_registered_and_not_stamped(rule):
    assert not _registrations_for(rule).exists()
    rule = RegistrationRule._base_manager.get(pk=rule.pk)
    assert rule.last_evaluated_at is None


@pytest.mark.django_db
def test_registers_nobody_while_the_organisation_switch_is_off(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=False
    )
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    _assert_nothing_registered_and_not_stamped(rule)


@pytest.mark.django_db
def test_registers_nobody_while_the_organisation_has_no_settings_row(
    mock_site_context,
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    OrganisationHRSettings._base_manager.filter(organisation=rule.organisation).delete()
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    _assert_nothing_registered_and_not_stamped(rule)


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


@pytest.fixture
def on_first_registration_saved():
    """Return a function that runs an action on the first LearnerCourseRegistration save.

    The receiver is disconnected at teardown.
    """
    receivers = []

    def connect(action):
        calls: list[int] = []

        def receiver(sender, instance, created, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                action()

        post_save.connect(receiver, sender=LearnerCourseRegistration, weak=False)
        receivers.append(receiver)

    yield connect

    for receiver in receivers:
        post_save.disconnect(receiver, sender=LearnerCourseRegistration)


@pytest.mark.django_db
def test_a_rule_disabled_between_batches_registers_nobody_afterwards(
    mock_site_context, settings, on_first_registration_saved
):
    # Arrange
    settings.REGISTRATION_RULE_BATCH_SIZE = 2
    rule = _enabled_rule()
    LearnerFactory.create_batch(5, organisation=rule.organisation)
    drop_ambient_request()
    on_first_registration_saved(
        lambda: RegistrationRule._base_manager.filter(pk=rule.pk).update(
            is_enabled=False
        )
    )

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _registrations_for(rule).count() == 2


@pytest.mark.django_db
def test_a_switch_turned_off_between_batches_stops_the_run(
    mock_site_context, settings, on_first_registration_saved
):
    # Arrange
    settings.REGISTRATION_RULE_BATCH_SIZE = 2
    rule = _enabled_rule()
    LearnerFactory.create_batch(5, organisation=rule.organisation)
    drop_ambient_request()
    on_first_registration_saved(
        lambda: OrganisationHRSettings._base_manager.filter(
            organisation=rule.organisation
        ).update(registration_rules_enabled=False)
    )

    # Act
    evaluate_rule(rule.pk, rule.site_id)

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
    other_site = SiteFactory()
    foreign = LearnerFactory(organisation=rule.organisation)
    Learner._base_manager.filter(pk=foreign.pk).update(site=other_site)
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
    other_site = SiteFactory()
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
