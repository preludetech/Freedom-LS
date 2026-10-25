"""Tests for evaluating a registration rule."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import time_machine

from django.db import connection
from django.db.models.signals import post_save
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from freedom_ls.comms.models import Notification
from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.hr_attributes.factories import (
    JobTitleFactory,
    LearnerHRAttributesFactory,
    OrganisationHRSettingsFactory,
)
from freedom_ls.hr_attributes.models import OrganisationHRSettings
from freedom_ls.learner_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.factories import SiteFactory
from freedom_ls.webhooks.models import WebhookEvent

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.registration_rules.evaluation import (
    EvaluationResult,
    apply_rule_changes,
    classify_rule_changes,
    evaluate_learner,
    evaluate_organisation,
    evaluate_rule,
)
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRecommendationFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.kinds import RuleState
from freedom_ls.registration_rules.models import (
    RegistrationRule,
    RuleRecommendation,
    RuleRegistration,
)
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
def test_registers_a_matching_learner(rule_run_for_one_learner):
    # Arrange
    rule, learner, _ = rule_run_for_one_learner

    # Act
    registration = _registrations_for(rule).get(learner=learner)

    # Assert
    assert registration.is_active is True
    assert registration.self_registered is False


@pytest.mark.django_db
def test_a_registered_learner_is_linked_to_the_rule(rule_run_for_one_learner):
    # Arrange
    rule, learner, _ = rule_run_for_one_learner

    # Act
    registration = _registrations_for(rule).get(learner=learner)
    link = RuleRegistration._base_manager.get(registration=registration)

    # Assert
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


@pytest.fixture
def organisation_with_rules_on(mock_site_context):
    return OrganisationHRSettingsFactory(registration_rules_enabled=True).organisation


@pytest.fixture
def job_title(organisation_with_rules_on):
    return JobTitleFactory(organisation=organisation_with_rules_on)


@pytest.fixture
def title_rule(organisation_with_rules_on, job_title):
    """An enabled rule that matches only learners holding `job_title`."""
    rule = RegistrationRuleFactory(
        organisation=organisation_with_rules_on, is_enabled=True
    )
    AttributeRuleConditionsFactory(rule=rule, job_titles=[job_title])
    return rule


@pytest.fixture
def unmatched_learner(organisation_with_rules_on):
    """A learner holding no job title, so title_rule does not match them."""
    return LearnerFactory(organisation=organisation_with_rules_on)


def _rule_made_registration(rule, learner, *, is_active=True, is_retracted=False):
    registration = LearnerCourseRegistrationFactory(
        learner=learner,
        course=rule.course,
        is_active=is_active,
        self_registered=False,
    )
    link = RuleRegistrationFactory(
        rule=rule, registration=registration, is_retracted=is_retracted
    )
    return registration, link


@pytest.mark.django_db
def test_retracts_an_unstarted_learner_who_stopped_matching(
    title_rule, unmatched_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, unmatched_learner)
    drop_ambient_request()

    # Act
    result = evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False
    assert result.retracted == (unmatched_learner.pk,)


@pytest.mark.django_db
def test_a_retracted_registration_is_marked_retracted(title_rule, unmatched_learner):
    # Arrange
    _, link = _rule_made_registration(title_rule, unmatched_learner)
    drop_ambient_request()

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    link.refresh_from_db()
    assert link.is_retracted is True
    assert link.rule == title_rule


@pytest.mark.django_db
def test_keeps_the_registration_of_a_learner_who_started_the_course(
    title_rule, unmatched_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, unmatched_learner)
    CourseProgressFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        learner_registration=registration,
        progress_percentage=10,
    )
    drop_ambient_request()

    # Act
    result = evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is True
    assert result.retracted == ()


@pytest.mark.django_db
def test_retracting_keeps_the_learners_progress_record(title_rule, unmatched_learner):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, unmatched_learner)
    progress = CourseProgressFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        learner_registration=registration,
    )
    drop_ambient_request()

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    assert CourseProgress._base_manager.filter(pk=progress.pk).exists()


@pytest.mark.django_db
def test_classification_reports_a_started_learner_as_kept(
    title_rule, unmatched_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, unmatched_learner)
    CourseProgressFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        learner_registration=registration,
        progress_percentage=10,
    )
    drop_ambient_request()

    # Act
    changes = classify_rule_changes(title_rule, RuleState.from_rule(title_rule))

    # Assert
    assert changes.kept_started == (unmatched_learner.pk,)
    assert changes.retract == ()


@pytest.mark.django_db
def test_classification_reports_the_rule_that_takes_a_learner_over(
    organisation_with_rules_on, unmatched_learner
):
    # Arrange
    owner = RegistrationRuleFactory(
        organisation=organisation_with_rules_on, is_enabled=False
    )
    taker = RegistrationRuleFactory(
        organisation=organisation_with_rules_on,
        course=owner.course,
        is_enabled=True,
        name="Taker",
    )
    _rule_made_registration(owner, unmatched_learner)
    drop_ambient_request()

    # Act
    changes = classify_rule_changes(owner, RuleState.from_rule(owner))

    # Assert
    (hand_over,) = changes.hand_over
    assert hand_over.learner_id == unmatched_learner.pk
    assert hand_over.rule_id == taker.pk
    assert hand_over.rule_name == "Taker"


@pytest.mark.django_db
def test_reactivates_a_retracted_registration_on_the_same_row(
    title_rule, job_title, unmatched_learner
):
    # Arrange
    registration, link = _rule_made_registration(
        title_rule, unmatched_learner, is_active=False, is_retracted=True
    )
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    drop_ambient_request()

    # Act
    result = evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert registration.is_active is True
    assert link.is_retracted is False
    assert result.reactivated == (unmatched_learner.pk,)
    assert _registrations_for(title_rule).count() == 1


@pytest.mark.django_db
def test_reactivating_keeps_the_progress_record_unchanged(
    title_rule, job_title, unmatched_learner
):
    # Arrange
    registration, _ = _rule_made_registration(
        title_rule, unmatched_learner, is_active=False, is_retracted=True
    )
    progress = CourseProgressFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        learner_registration=registration,
        progress_percentage=40,
    )
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    drop_ambient_request()

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    assert (
        CourseProgress._base_manager.filter(course=title_rule.course).get() == progress
    )
    progress.refresh_from_db()
    assert progress.progress_percentage == 40


@pytest.mark.django_db
def test_reactivating_raises_no_notification(
    title_rule, job_title, unmatched_learner, django_capture_on_commit_callbacks
):
    # Arrange
    _rule_made_registration(
        title_rule, unmatched_learner, is_active=False, is_retracted=True
    )
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    assert not Notification._base_manager.filter(
        user=unmatched_learner.user, category="course.registered"
    ).exists()


@pytest.mark.django_db
def test_reactivating_announces_course_registered_to_integrators(
    title_rule,
    job_title,
    unmatched_learner,
    settings,
    django_capture_on_commit_callbacks,
):
    # Arrange
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    registration, _ = _rule_made_registration(
        title_rule, unmatched_learner, is_active=False, is_retracted=True
    )
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    WebhookEvent._base_manager.all().delete()
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    event = WebhookEvent._base_manager.get(event_type="course.registered")
    assert event.site_id == title_rule.site_id
    assert event.payload["course_id"] == str(registration.course_id)
    assert event.payload["user_id"] == unmatched_learner.user_id


@pytest.mark.django_db
def test_retracting_announces_course_unregistered_to_integrators(
    title_rule, unmatched_learner, settings, django_capture_on_commit_callbacks
):
    # Arrange
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    registration, _ = _rule_made_registration(title_rule, unmatched_learner)
    WebhookEvent._base_manager.all().delete()
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    event = WebhookEvent._base_manager.get(event_type="course.unregistered")
    assert event.site_id == title_rule.site_id
    assert event.payload["course_id"] == str(registration.course_id)
    assert event.payload["learner_id"] == str(unmatched_learner.pk)


@pytest.mark.django_db
def test_hands_a_learner_to_another_enabled_rule_and_keeps_them_registered(
    organisation_with_rules_on, unmatched_learner
):
    # Arrange
    owner = RegistrationRuleFactory(
        organisation=organisation_with_rules_on, is_enabled=False
    )
    taker = RegistrationRuleFactory(
        organisation=organisation_with_rules_on, course=owner.course, is_enabled=True
    )
    registration, link = _rule_made_registration(owner, unmatched_learner)
    drop_ambient_request()

    # Act
    evaluate_rule(owner.pk, owner.site_id)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert registration.is_active is True
    assert link.rule == taker
    assert link.rule_name == taker.name
    assert link.is_retracted is False


@pytest.mark.django_db
def test_retracts_a_learner_when_no_other_enabled_rule_takes_them(
    organisation_with_rules_on, unmatched_learner
):
    # Arrange
    owner = RegistrationRuleFactory(
        organisation=organisation_with_rules_on, is_enabled=False
    )
    RegistrationRuleFactory(
        organisation=organisation_with_rules_on, course=owner.course, is_enabled=False
    )
    registration, _ = _rule_made_registration(owner, unmatched_learner)
    drop_ambient_request()

    # Act
    evaluate_rule(owner.pk, owner.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_never_reactivates_a_registration_staff_deactivated(
    title_rule, job_title, unmatched_learner
):
    # Arrange
    registration = LearnerCourseRegistrationFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        is_active=False,
        self_registered=False,
    )
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    drop_ambient_request()

    # Act
    result = evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False
    assert result.reactivated == ()


@pytest.mark.django_db
def test_never_retracts_a_registration_whose_rule_was_deleted(
    title_rule, unmatched_learner
):
    # Arrange
    registration, link = _rule_made_registration(title_rule, unmatched_learner)
    RuleRegistration._base_manager.filter(pk=link.pk).update(rule=None)
    drop_ambient_request()

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is True


@pytest.mark.django_db
def test_a_run_over_a_retracted_registration_that_still_does_not_match_changes_nothing(
    title_rule, unmatched_learner
):
    # Arrange
    registration, link = _rule_made_registration(
        title_rule, unmatched_learner, is_active=False, is_retracted=True
    )
    drop_ambient_request()

    # Act
    result = evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert result.retracted == ()
    assert result.reactivated == ()
    assert registration.is_active is False
    assert link.is_retracted is True


@pytest.fixture
def titled_learner(organisation_with_rules_on, job_title):
    """A learner holding `job_title`, so title_rule matches them."""
    learner = LearnerFactory(organisation=organisation_with_rules_on)
    LearnerHRAttributesFactory(learner=learner, job_title=job_title)
    return learner


@pytest.fixture
def other_organisation_rule(mock_site_context):
    """An enabled rule with no conditions in a second organisation whose switch is on."""
    rule = RegistrationRuleFactory(organisation=OrganisationFactory(), is_enabled=True)
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=True
    )
    return rule


def _move_learner(learner, organisation):
    learner.organisation = organisation
    learner.save()


@pytest.mark.django_db
def test_evaluating_a_learner_registers_them_once_their_attributes_match(
    title_rule, job_title, unmatched_learner
):
    # Arrange
    LearnerHRAttributesFactory(learner=unmatched_learner, job_title=job_title)
    drop_ambient_request()

    # Act
    result = evaluate_learner(unmatched_learner.pk, unmatched_learner.site_id)

    # Assert
    assert result.registered == (unmatched_learner.pk,)
    assert _registrations_for(title_rule).filter(learner=unmatched_learner).exists()


@pytest.mark.django_db
def test_evaluating_a_learner_retracts_them_once_their_attributes_stop_matching(
    title_rule, titled_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, titled_learner)
    titled_learner.hr_attributes.job_title = JobTitleFactory(
        organisation=title_rule.organisation
    )
    titled_learner.hr_attributes.save()
    drop_ambient_request()

    # Act
    result = evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    registration.refresh_from_db()
    assert result.retracted == (titled_learner.pk,)
    assert registration.is_active is False


@pytest.mark.django_db
def test_evaluating_a_learner_who_moved_retracts_them_from_the_old_organisations_rule(
    title_rule, titled_learner, other_organisation_rule
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, titled_learner)
    _move_learner(titled_learner, other_organisation_rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_evaluating_a_learner_who_moved_registers_them_with_the_new_organisations_rule(
    titled_learner, other_organisation_rule
):
    # Arrange
    _move_learner(titled_learner, other_organisation_rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    assert (
        _registrations_for(other_organisation_rule)
        .filter(learner=titled_learner, is_active=True)
        .exists()
    )


@pytest.mark.django_db
def test_evaluating_a_learner_who_moved_leaves_a_registration_of_an_organisation_whose_switch_is_off(
    title_rule, titled_learner, other_organisation_rule
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, titled_learner)
    _move_learner(titled_learner, other_organisation_rule.organisation)
    OrganisationHRSettings._base_manager.filter(
        organisation=title_rule.organisation
    ).update(registration_rules_enabled=False)
    drop_ambient_request()

    # Act
    evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is True


@pytest.mark.django_db
def test_evaluating_a_learner_retracts_them_once_they_are_inactive(
    title_rule, titled_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, titled_learner)
    titled_learner.is_active = False
    titled_learner.save()
    drop_ambient_request()

    # Act
    evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_evaluating_a_learner_does_nothing_while_their_organisations_switch_is_off(
    title_rule, titled_learner
):
    # Arrange
    OrganisationHRSettings._base_manager.filter(
        organisation=title_rule.organisation
    ).update(registration_rules_enabled=False)
    drop_ambient_request()

    # Act
    result = evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    assert result.registered == ()
    assert not _registrations_for(title_rule).exists()


@pytest.mark.django_db
def test_evaluating_a_learner_who_no_longer_exists_returns_an_empty_result(
    title_rule, titled_learner
):
    # Arrange
    learner_id, site_id = titled_learner.pk, titled_learner.site_id
    Learner._base_manager.filter(pk=learner_id).delete()
    drop_ambient_request()

    # Act
    result = evaluate_learner(learner_id, site_id)

    # Assert
    assert result == EvaluationResult()


@pytest.mark.django_db
def test_evaluating_an_organisation_registers_a_learner_who_matches_and_was_never_evaluated(
    title_rule, titled_learner
):
    # Arrange
    drop_ambient_request()

    # Act
    result = evaluate_organisation(title_rule.organisation_id, title_rule.site_id)

    # Assert
    assert result.registered == (titled_learner.pk,)


@pytest.mark.django_db
def test_evaluating_an_organisation_retracts_the_registrations_of_a_disabled_rule(
    title_rule, titled_learner
):
    # Arrange
    registration, _ = _rule_made_registration(title_rule, titled_learner)
    RegistrationRule._base_manager.filter(pk=title_rule.pk).update(is_enabled=False)
    drop_ambient_request()

    # Act
    evaluate_organisation(title_rule.organisation_id, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False


@pytest.mark.django_db
def test_evaluating_an_organisation_leaves_another_organisations_rules_alone(
    title_rule, other_organisation_rule
):
    # Arrange
    bystander = LearnerFactory(organisation=other_organisation_rule.organisation)
    drop_ambient_request()

    # Act
    evaluate_organisation(title_rule.organisation_id, title_rule.site_id)

    # Assert
    assert (
        not _registrations_for(other_organisation_rule)
        .filter(learner=bystander)
        .exists()
    )


def _locking_queries(captured):
    return [q["sql"] for q in captured.captured_queries if " FOR " in q["sql"]]


@pytest.mark.django_db
def test_a_rule_run_locks_the_rule_without_blocking_foreign_key_checks(
    title_rule, titled_learner
):
    # Arrange
    drop_ambient_request()

    # Act
    with CaptureQueriesContext(connection) as captured:
        evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    locks = _locking_queries(captured)
    assert locks
    assert all("FOR NO KEY UPDATE" in sql for sql in locks)


@pytest.mark.django_db
def test_a_learner_run_locks_the_learner_without_blocking_foreign_key_checks(
    title_rule, titled_learner
):
    # Arrange
    drop_ambient_request()

    # Act
    with CaptureQueriesContext(connection) as captured:
        evaluate_learner(titled_learner.pk, titled_learner.site_id)

    # Assert
    locks = _locking_queries(captured)
    assert locks
    assert all("FOR NO KEY UPDATE" in sql for sql in locks)


@pytest.fixture
def learner_moved_between_organisations_with_rules_on_one_course(
    title_rule, unmatched_learner, other_organisation_rule
):
    """A learner registered by title_rule who moved to an organisation whose rule
    targets the same course and matches everyone."""
    other_organisation_rule.course = title_rule.course
    other_organisation_rule.save()
    registration, link = _rule_made_registration(title_rule, unmatched_learner)
    _move_learner(unmatched_learner, other_organisation_rule.organisation)
    drop_ambient_request()
    return registration, link, other_organisation_rule


@pytest.mark.django_db
def test_the_old_organisations_rule_hands_a_moved_learner_to_the_new_organisations_rule(
    learner_moved_between_organisations_with_rules_on_one_course, title_rule
):
    # Arrange
    registration, link, new_rule = (
        learner_moved_between_organisations_with_rules_on_one_course
    )

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert registration.is_active is True
    assert link.rule == new_rule


@pytest.mark.django_db
def test_the_old_organisations_rule_keeps_a_moved_learner_whose_new_switch_is_off(
    learner_moved_between_organisations_with_rules_on_one_course, title_rule
):
    # Arrange
    registration, link, new_rule = (
        learner_moved_between_organisations_with_rules_on_one_course
    )
    OrganisationHRSettings._base_manager.filter(
        organisation=new_rule.organisation
    ).update(registration_rules_enabled=False)

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert registration.is_active is False
    assert link.rule == title_rule


@pytest.mark.django_db
def test_a_learner_who_starts_the_course_after_classification_is_not_retracted(
    title_rule, unmatched_learner
):
    # Arrange
    registration, link = _rule_made_registration(title_rule, unmatched_learner)
    changes = classify_rule_changes(title_rule, RuleState.from_rule(title_rule))
    CourseProgressFactory(
        learner=unmatched_learner,
        course=title_rule.course,
        learner_registration=registration,
        progress_percentage=10,
    )
    drop_ambient_request()

    # Act
    result = apply_rule_changes(title_rule, changes)

    # Assert
    registration.refresh_from_db()
    link.refresh_from_db()
    assert changes.retract == (unmatched_learner.pk,)
    assert registration.is_active is True
    assert link.is_retracted is False
    assert result.retracted == ()


@pytest.mark.django_db
def test_a_rule_edited_during_a_run_still_shows_its_change_as_not_applied(
    title_rule, titled_learner, monkeypatch
):
    # Arrange
    from freedom_ls.registration_rules import evaluation

    classify = evaluation.classify_rule_changes

    def classify_then_edit(rule, state, learner_ids=None):
        RegistrationRule._base_manager.filter(pk=rule.pk).update(
            updated_at=timezone.now()
        )
        return classify(rule, state, learner_ids=learner_ids)

    monkeypatch.setattr(evaluation, "classify_rule_changes", classify_then_edit)
    drop_ambient_request()

    # Act
    evaluate_rule(title_rule.pk, title_rule.site_id)

    # Assert
    rule = RegistrationRule._base_manager.get(pk=title_rule.pk)
    assert rule.last_evaluated_at is not None
    assert rule.last_evaluated_at < rule.updated_at


def _recommend_rule(**overrides):
    return _enabled_rule(outcome=RegistrationRule.Outcome.RECOMMEND, **overrides)


def _recommendations_for(rule):
    return RecommendedCourse._base_manager.filter(course=rule.course)


@pytest.mark.django_db
def test_a_recommend_rule_recommends_the_course_to_each_matching_user_and_registers_nobody(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learners = LearnerFactory.create_batch(2, organisation=rule.organisation)
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert set(_recommendations_for(rule).values_list("user_id", flat=True)) == {
        learner.user_id for learner in learners
    }
    assert RuleRecommendation._base_manager.filter(rule=rule).count() == 2
    assert not _registrations_for(rule).exists()
    assert not RuleRegistration._base_manager.filter(rule=rule).exists()
    assert sorted(result.recommended) == sorted(learner.user_id for learner in learners)


@pytest.mark.django_db
def test_a_second_run_of_a_recommend_rule_creates_nothing(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result == EvaluationResult()
    assert _recommendations_for(rule).count() == 1


@pytest.mark.django_db
def test_a_recommend_rule_skips_a_user_registered_individually(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=rule.course)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_recommend_rule_skips_a_user_registered_through_a_cohort(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    cohort = CohortFactory(organisation=rule.organisation)
    learner = LearnerFactory(organisation=rule.organisation)
    CohortMembershipFactory(cohort=cohort, learner=learner)
    CohortCourseRegistrationFactory(cohort=cohort, course=rule.course)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_recommend_rule_skips_a_user_registered_through_their_learner_in_another_organisation(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    elsewhere = LearnerFactory(user=learner.user)
    LearnerCourseRegistrationFactory(learner=elsewhere, course=rule.course)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_rule_made_recommendation_for_a_user_registered_by_bulk_create_is_removed(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)
    LearnerCourseRegistration._base_manager.bulk_create(
        [
            LearnerCourseRegistration(
                site_id=rule.site_id,
                learner=learner,
                course=rule.course,
                is_active=True,
            )
        ]
    )

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result.recommendations_removed == (learner.user_id,)
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_user_who_stops_matching_loses_the_rule_made_recommendation(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    other_organisation = OrganisationFactory()
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)
    Learner._base_manager.filter(pk=learner.pk).update(organisation=other_organisation)

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result.recommendations_removed == (learner.user_id,)
    assert not _recommendations_for(rule).exists()
    assert not RuleRecommendation._base_manager.filter(rule=rule).exists()


@pytest.mark.django_db
def test_disabling_a_recommend_rule_removes_every_recommendation_it_made(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    LearnerFactory.create_batch(2, organisation=rule.organisation)
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)
    RegistrationRule._base_manager.filter(pk=rule.pk).update(is_enabled=False)

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert len(result.recommendations_removed) == 2
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_matching_users_staff_made_recommendation_is_left_alone(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    staff_made = RecommendedCourseFactory(user=learner.user, course=rule.course)
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result == EvaluationResult()
    assert list(_recommendations_for(rule)) == [staff_made]
    assert not RuleRecommendation._base_manager.filter(rule=rule).exists()


@pytest.mark.django_db
def test_a_staff_made_recommendation_survives_the_user_no_longer_matching(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    RecommendedCourseFactory(user=learner.user, course=rule.course)
    Learner._base_manager.filter(pk=learner.pk).update(
        organisation=OrganisationFactory()
    )
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _recommendations_for(rule).count() == 1


@pytest.mark.django_db
def test_a_staff_made_recommendation_survives_disabling_the_rule(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    RecommendedCourseFactory(user=learner.user, course=rule.course)
    RegistrationRule._base_manager.filter(pk=rule.pk).update(is_enabled=False)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _recommendations_for(rule).count() == 1


@pytest.mark.django_db
def test_evaluating_a_learner_recommends_the_course_to_their_user(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()

    # Act
    result = evaluate_learner(learner.pk, rule.site_id)

    # Assert
    assert result.recommended == (learner.user_id,)
    assert _recommendations_for(rule).get().user_id == learner.user_id
    assert not _registrations_for(rule).exists()


@pytest.mark.django_db
def test_evaluating_a_learner_removes_a_recommendation_their_rule_no_longer_matches(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    RuleRecommendationFactory(
        rule=rule,
        recommendation=RecommendedCourseFactory(user=learner.user, course=rule.course),
    )
    Learner._base_manager.filter(pk=learner.pk).update(
        organisation=OrganisationFactory()
    )
    drop_ambient_request()

    # Act
    result = evaluate_learner(learner.pk, rule.site_id)

    # Assert
    assert result.recommendations_removed == (learner.user_id,)
    assert not _recommendations_for(rule).exists()


@pytest.mark.django_db
def test_a_register_rule_does_not_hand_a_registration_to_a_recommend_rule_on_its_course(
    mock_site_context,
):
    # Arrange
    register_rule = _enabled_rule()
    new_organisation = OrganisationFactory()
    _recommend_rule(organisation=new_organisation, course=register_rule.course)
    learner = LearnerFactory(organisation=register_rule.organisation)
    RuleRegistrationFactory(
        rule=register_rule,
        registration=LearnerCourseRegistrationFactory(
            learner=learner, course=register_rule.course, self_registered=False
        ),
    )
    Learner._base_manager.filter(pk=learner.pk).update(organisation=new_organisation)
    drop_ambient_request()

    # Act
    result = evaluate_rule(register_rule.pk, register_rule.site_id)

    # Assert
    assert result.retracted == (learner.pk,)
    assert RuleRegistration._base_manager.get(rule=register_rule).is_retracted is True


@pytest.mark.django_db
def test_a_recommend_rule_run_touches_only_the_given_site(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    own = LearnerFactory(organisation=rule.organisation)
    foreign = LearnerFactory(organisation=rule.organisation)
    Learner._base_manager.filter(pk=foreign.pk).update(site=SiteFactory())
    drop_ambient_request()

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result.recommended == (own.user_id,)
    assert [row.user_id for row in _recommendations_for(rule)] == [own.user_id]
    assert _recommendations_for(rule).get().site_id == rule.site_id


@pytest.fixture
def two_organisations_recommending(mock_site_context):
    """One user in two organisations, each with a recommend rule on the same course."""
    rule_a = _recommend_rule()
    rule_b = _recommend_rule(organisation=OrganisationFactory(), course=rule_a.course)
    learner_a = LearnerFactory(organisation=rule_a.organisation)
    learner_b = LearnerFactory(user=learner_a.user, organisation=rule_b.organisation)
    drop_ambient_request()
    return rule_a, rule_b, learner_a, learner_b


def _held_by(rule):
    return list(
        RuleRecommendation._base_manager.filter(rule=rule).values_list(
            "recommendation__user_id", flat=True
        )
    )


def _after_classifying(monkeypatch, mutate):
    """Run `mutate` between the classifying read and the write of every recommend run."""
    from freedom_ls.registration_rules import evaluation

    classify = evaluation.classify_recommendation_changes

    def classify_then_mutate(rule, state, user_ids=None):
        changes = classify(rule, state, user_ids=user_ids)
        mutate()
        return changes

    monkeypatch.setattr(
        evaluation, "classify_recommendation_changes", classify_then_mutate
    )


@pytest.mark.django_db
def test_rules_of_two_organisations_share_one_recommendation(
    two_organisations_recommending,
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending

    # Act
    evaluate_rule(rule_a.pk, rule_a.site_id)
    evaluate_rule(rule_b.pk, rule_b.site_id)

    # Assert
    assert _recommendations_for(rule_a).get().user_id == learner_a.user_id
    assert _held_by(rule_a) == [learner_a.user_id]
    assert _held_by(rule_b) == [learner_a.user_id]


@pytest.mark.django_db
def test_one_rule_unmatching_leaves_the_recommendation_with_the_other_rules_row(
    two_organisations_recommending,
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending
    evaluate_rule(rule_a.pk, rule_a.site_id)
    evaluate_rule(rule_b.pk, rule_b.site_id)
    RegistrationRule._base_manager.filter(pk=rule_a.pk).update(is_enabled=False)

    # Act
    result = evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    assert result.recommendations_removed == ()
    assert _recommendations_for(rule_a).get().user_id == learner_a.user_id
    assert _held_by(rule_a) == []
    assert _held_by(rule_b) == [learner_a.user_id]


@pytest.mark.django_db
def test_the_last_rule_to_unmatch_deletes_the_recommendation(
    two_organisations_recommending,
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending
    evaluate_rule(rule_a.pk, rule_a.site_id)
    evaluate_rule(rule_b.pk, rule_b.site_id)
    RegistrationRule._base_manager.filter(pk__in=[rule_a.pk, rule_b.pk]).update(
        is_enabled=False
    )
    evaluate_rule(rule_a.pk, rule_a.site_id)

    # Act
    result = evaluate_rule(rule_b.pk, rule_b.site_id)

    # Assert
    assert result.recommendations_removed == (learner_a.user_id,)
    assert not _recommendations_for(rule_a).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_evaluating_both_learners_of_one_user_back_to_back_gives_the_same_rows(
    two_organisations_recommending,
):
    # Arrange
    rule_a, rule_b, learner_a, learner_b = two_organisations_recommending

    # Act
    evaluate_learner(learner_a.pk, rule_a.site_id)
    evaluate_learner(learner_b.pk, rule_a.site_id)

    # Assert
    assert _recommendations_for(rule_a).get().user_id == learner_a.user_id
    assert _held_by(rule_a) == [learner_a.user_id]
    assert _held_by(rule_b) == [learner_a.user_id]


@pytest.mark.django_db
def test_two_enabled_rules_in_one_organisation_share_a_recommendation(
    mock_site_context,
):
    # Arrange
    rule_one = _recommend_rule()
    rule_two = RegistrationRuleFactory(
        is_enabled=True,
        outcome=RegistrationRule.Outcome.RECOMMEND,
        organisation=rule_one.organisation,
        course=rule_one.course,
    )
    learner = LearnerFactory(organisation=rule_one.organisation)
    drop_ambient_request()
    evaluate_rule(rule_one.pk, rule_one.site_id)
    evaluate_rule(rule_two.pk, rule_two.site_id)
    RegistrationRule._base_manager.filter(pk=rule_one.pk).update(is_enabled=False)

    # Act
    evaluate_rule(rule_one.pk, rule_one.site_id)

    # Assert
    assert _recommendations_for(rule_one).get().user_id == learner.user_id
    assert _held_by(rule_one) == []
    assert _held_by(rule_two) == [learner.user_id]


@pytest.mark.django_db
def test_a_rule_does_not_join_a_staff_made_recommendation(mock_site_context):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    RecommendedCourseFactory(user=learner.user, course=rule.course)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_a_create_that_finds_a_rule_made_row_made_meanwhile_joins_it(
    two_organisations_recommending, monkeypatch
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending

    def other_rule_recommends_first():
        recommendation, _ = RecommendedCourse._base_manager.get_or_create(
            site_id=rule_b.site_id,
            user_id=learner_a.user_id,
            course_id=rule_a.course_id,
        )
        RuleRecommendation._base_manager.get_or_create(
            site_id=rule_b.site_id, rule=rule_b, recommendation=recommendation
        )

    _after_classifying(monkeypatch, other_rule_recommends_first)

    # Act
    result = evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    assert result.recommended == ()
    assert _held_by(rule_a) == [learner_a.user_id]
    assert _held_by(rule_b) == [learner_a.user_id]


@pytest.mark.django_db
def test_a_create_that_finds_a_staff_made_row_made_meanwhile_skips_it(
    mock_site_context, monkeypatch
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    _after_classifying(
        monkeypatch,
        lambda: RecommendedCourse._base_manager.get_or_create(
            site_id=rule.site_id, user_id=learner.user_id, course_id=rule.course_id
        ),
    )

    # Act
    result = evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert result.recommended == ()
    assert _recommendations_for(rule).count() == 1
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_a_remove_whose_row_gained_another_rules_hold_meanwhile_drops_only_its_own(
    two_organisations_recommending, monkeypatch
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending
    evaluate_rule(rule_a.pk, rule_a.site_id)
    RegistrationRule._base_manager.filter(pk=rule_a.pk).update(is_enabled=False)
    _after_classifying(
        monkeypatch,
        lambda: RuleRecommendation._base_manager.get_or_create(
            site_id=rule_b.site_id,
            rule=rule_b,
            recommendation=_recommendations_for(rule_a).get(),
        ),
    )

    # Act
    result = evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    assert result.recommendations_removed == ()
    assert _recommendations_for(rule_a).get().user_id == learner_a.user_id
    assert _held_by(rule_a) == []
    assert _held_by(rule_b) == [learner_a.user_id]


@pytest.mark.django_db
def test_a_drop_whose_row_lost_the_other_rules_hold_meanwhile_deletes_the_row(
    two_organisations_recommending, monkeypatch
):
    # Arrange
    rule_a, rule_b, learner_a, _ = two_organisations_recommending
    evaluate_rule(rule_a.pk, rule_a.site_id)
    evaluate_rule(rule_b.pk, rule_b.site_id)
    RegistrationRule._base_manager.filter(pk=rule_a.pk).update(is_enabled=False)
    _after_classifying(
        monkeypatch,
        lambda: RuleRecommendation._base_manager.filter(rule=rule_b).delete(),
    )

    # Act
    result = evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    assert result.recommendations_removed == (learner_a.user_id,)
    assert not _recommendations_for(rule_a).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_a_drop_that_finds_the_row_deleted_meanwhile_does_nothing(
    two_organisations_recommending, monkeypatch
):
    # Arrange
    rule_a, rule_b, _, _ = two_organisations_recommending
    evaluate_rule(rule_a.pk, rule_a.site_id)
    evaluate_rule(rule_b.pk, rule_b.site_id)
    RegistrationRule._base_manager.filter(pk=rule_a.pk).update(is_enabled=False)
    _after_classifying(monkeypatch, lambda: _recommendations_for(rule_a).delete())

    # Act
    result = evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    assert result == EvaluationResult()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_an_add_that_finds_the_row_deleted_meanwhile_leaves_no_dangling_hold(
    two_organisations_recommending, monkeypatch
):
    # Arrange
    rule_a, rule_b, _, _ = two_organisations_recommending
    evaluate_rule(rule_b.pk, rule_b.site_id)
    _after_classifying(monkeypatch, lambda: _recommendations_for(rule_a).delete())

    # Act
    evaluate_rule(rule_a.pk, rule_a.site_id)

    # Assert
    connection.check_constraints()
    assert not RuleRecommendation._base_manager.filter(rule=rule_a).exists()


@pytest.mark.django_db
def test_a_rule_made_recommendation_deleted_by_hand_comes_back_while_the_user_matches(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)
    _recommendations_for(rule).delete()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _recommendations_for(rule).get().user_id == learner.user_id
    assert _held_by(rule) == [learner.user_id]


@pytest.mark.django_db
def test_a_staff_made_recommendation_deleted_by_hand_does_not_come_back(
    mock_site_context,
):
    # Arrange
    rule = _recommend_rule()
    learner = LearnerFactory(organisation=rule.organisation)
    Learner._base_manager.filter(pk=learner.pk).update(
        organisation=OrganisationFactory()
    )
    RecommendedCourseFactory(user=learner.user, course=rule.course)
    drop_ambient_request()
    evaluate_rule(rule.pk, rule.site_id)
    _recommendations_for(rule).delete()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert not _recommendations_for(rule).exists()
