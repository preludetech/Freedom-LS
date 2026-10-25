"""Tests for the registration rule signal receivers."""

from __future__ import annotations

import contextlib
from datetime import UTC, date, datetime

import pytest
import time_machine

from django.core import serializers
from django.db import connection, transaction
from django.db.models import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.course_recommendations.factories import RecommendedCourseFactory
from freedom_ls.course_recommendations.models import RecommendedCourse
from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
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
from freedom_ls.learner_management.models import (
    Cohort,
    CohortCourseRegistration,
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.registration_rules.evaluation import (
    evaluate_organisation,
    evaluate_rule,
)
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRecommendationFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import (
    RegistrationRule,
    RuleRecommendation,
    RuleRegistration,
)
from freedom_ls.registration_rules.tasks import evaluate_learner_task
from freedom_ls.tests.site_context import drop_ambient_request


@pytest.fixture
def database_task_backend(settings) -> None:
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}


def _queued_tasks(task_name: str = "evaluate_rule_task"):
    from django_tasks_db.models import DBTaskResult

    return DBTaskResult.objects.filter(
        task_path=f"freedom_ls.registration_rules.tasks.{task_name}"
    )


@pytest.mark.django_db
def test_saving_an_enabled_rule_queues_an_evaluation_after_commit(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=False)
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        rule.is_enabled = True
        rule.save()
        queued_before_commit = _queued_tasks().count()

    # Assert
    assert queued_before_commit == 0
    assert len(callbacks) == 1
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(rule.pk), rule.site_id]


@pytest.mark.django_db
def test_loading_a_fixture_queues_nothing(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)
    payload = serializers.serialize(
        "json", [RegistrationRule._base_manager.get(pk=rule.pk)]
    )
    RegistrationRule._base_manager.filter(pk=rule.pk).delete()
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        next(iter(serializers.deserialize("json", payload))).save()

    # Assert
    assert callbacks == []
    assert not _queued_tasks().exists()


@pytest.mark.django_db
def test_deleting_a_rule_snapshots_its_name_onto_its_registrations(mock_site_context):
    # Arrange
    link = RuleRegistrationFactory(rule__is_enabled=False, rule_name="stale")
    rule = link.rule
    name = rule.name

    # Act
    rule.delete()

    # Assert
    link = RuleRegistration.objects.get(pk=link.pk)
    assert link.rule is None
    assert link.rule_name == name


@pytest.mark.django_db
def test_saving_a_conditions_row_queues_an_evaluation_of_its_rule(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    conditions = AttributeRuleConditionsFactory()
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        conditions.organisation_start_on_or_after = date(2024, 1, 1)
        conditions.save()

    # Assert
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(conditions.rule_id), conditions.site_id]


@pytest.mark.django_db
def test_adding_an_entry_to_a_picker_queues_an_evaluation_of_the_rule(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    conditions = AttributeRuleConditionsFactory()
    entry = JobTitleFactory(organisation=conditions.rule.organisation)
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        conditions.job_titles.add(entry)

    # Assert
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(conditions.rule_id), conditions.site_id]


@pytest.mark.django_db
def test_adding_a_conditions_row_from_the_entry_side_queues_an_evaluation_of_the_rule(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    conditions = AttributeRuleConditionsFactory()
    entry = JobTitleFactory(organisation=conditions.rule.organisation)
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        entry.registration_rule_conditions.add(conditions)

    # Assert
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(conditions.rule_id), conditions.site_id]


@pytest.mark.django_db
def test_removing_an_entry_from_a_picker_queues_an_evaluation_of_the_rule(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    entry = JobTitleFactory()
    conditions = AttributeRuleConditionsFactory(
        rule__organisation=entry.organisation, job_titles=[entry]
    )
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        conditions.job_titles.remove(entry)

    # Assert
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(conditions.rule_id), conditions.site_id]


@pytest.mark.django_db
def test_clearing_an_entrys_conditions_from_the_entry_side_queues_an_evaluation_of_the_rule(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    """The rule loses its only entry and widens to the whole organisation;
    the run that applies that must be queued, and the change must read as
    unapplied until it starts."""
    # Arrange
    entry = JobTitleFactory()
    conditions = AttributeRuleConditionsFactory(
        rule__organisation=entry.organisation, job_titles=[entry]
    )
    RegistrationRule.objects.filter(pk=conditions.rule_id).update(
        last_evaluated_at=timezone.now()
    )
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        entry.registration_rule_conditions.clear()

    # Assert
    queued = _queued_tasks().get()
    assert queued.args_kwargs["args"] == [str(conditions.rule_id), conditions.site_id]
    rule = RegistrationRule.objects.get(pk=conditions.rule_id)
    assert rule.last_evaluated_at < rule.updated_at


REGISTRATION_CHANGE = (
    "admin:freedom_ls_learner_management_learnercourseregistration_change"
)


@pytest.fixture
def rule_made_registration(mock_site_context):
    """A rule-made registration, active, for a learner in the site's default organisation."""
    organisation = get_default_organisation(mock_site_context)
    OrganisationHRSettingsFactory(
        organisation=organisation, registration_rules_enabled=True
    )
    rule = RegistrationRuleFactory(organisation=organisation, is_enabled=True)
    AttributeRuleConditionsFactory(
        rule=rule, job_titles=[JobTitleFactory(organisation=organisation)]
    )
    registration = LearnerCourseRegistrationFactory(
        learner=LearnerFactory(organisation=organisation),
        course=rule.course,
        self_registered=False,
    )
    link = RuleRegistrationFactory(rule=rule, registration=registration)
    return link


def _admin_form_post(response, *, is_active: bool) -> dict[str, str]:
    """An admin change form's own values, with is_active set."""
    form = response.context["adminform"].form
    payload = {
        name: "" if form.initial.get(name) is None else str(form.initial.get(name))
        for name in form.fields
        if name != "is_active"
    }
    if is_active:
        payload["is_active"] = "on"
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    return payload


@pytest.mark.django_db
@pytest.mark.parametrize("is_active", [False, True])
def test_changing_is_active_in_the_admin_detaches_the_rule(
    staff_client, rule_made_registration, is_active
):
    # Arrange
    registration = rule_made_registration.registration
    LearnerCourseRegistration._base_manager.filter(pk=registration.pk).update(
        is_active=not is_active
    )
    url = reverse(REGISTRATION_CHANGE, args=[registration.pk])
    payload = _admin_form_post(staff_client.get(url), is_active=is_active)

    # Act
    response = staff_client.post(url, payload)

    # Assert
    assert response.status_code == 302
    assert not RuleRegistration._base_manager.filter(registration=registration).exists()


@pytest.mark.django_db
def test_saving_the_admin_form_without_changing_is_active_keeps_the_rule(
    staff_client, rule_made_registration
):
    # Arrange
    registration = rule_made_registration.registration
    url = reverse(REGISTRATION_CHANGE, args=[registration.pk])
    payload = _admin_form_post(staff_client.get(url), is_active=True)

    # Act
    response = staff_client.post(url, payload)

    # Assert
    assert response.status_code == 302
    assert RuleRegistration._base_manager.filter(registration=registration).exists()


@pytest.mark.django_db
def test_a_learner_registering_again_detaches_the_rule_from_a_retracted_row(
    mock_site_context, logged_in_client, rule_made_registration
):
    # Arrange
    registration = rule_made_registration.registration
    LearnerCourseRegistration._base_manager.filter(pk=registration.pk).update(
        is_active=False
    )
    RuleRegistration._base_manager.filter(pk=rule_made_registration.pk).update(
        is_retracted=True
    )
    client = logged_in_client(registration.learner.user)

    # Act
    client.post(
        reverse(
            "learner_interface:initiate_course_access",
            kwargs={"course_slug": registration.course.slug},
        )
    )

    # Assert
    assert not RuleRegistration._base_manager.filter(registration=registration).exists()


@pytest.mark.django_db
def test_saving_a_stale_instance_for_another_field_keeps_the_rule(
    mock_site_context, rule_made_registration
):
    """A view that loaded the row while it was active, then saved another
    field after the engine retracted it, has decided nothing about is_active."""
    # Arrange
    link = rule_made_registration
    stale = LearnerCourseRegistration.objects.get(pk=link.registration_id)
    drop_ambient_request()
    evaluate_rule(link.rule.pk, link.rule.site_id)

    # Act
    stale.self_registered = True
    stale.save(update_fields=["self_registered"])

    # Assert
    link.refresh_from_db()
    assert link.is_retracted is True
    assert link.registration.is_active is False


@pytest.mark.django_db
def test_a_detached_registration_is_left_alone_by_the_next_run(
    mock_site_context, rule_made_registration
):
    # Arrange
    link = rule_made_registration
    registration = link.registration
    registration.is_active = False
    registration.save()
    drop_ambient_request()

    # Act
    evaluate_rule(link.rule.pk, link.rule.site_id)

    # Assert
    registration.refresh_from_db()
    assert registration.is_active is False
    assert not RuleRegistration._base_manager.filter(registration=registration).exists()


@pytest.mark.django_db
def test_the_engines_own_update_keeps_the_rule_registration(
    mock_site_context, rule_made_registration
):
    # Arrange
    link = rule_made_registration
    drop_ambient_request()

    # Act
    evaluate_rule(link.rule.pk, link.rule.site_id)

    # Assert
    link.refresh_from_db()
    assert link.is_retracted is True
    assert link.registration.is_active is False


@pytest.fixture
def organisation_using_rules(mock_site_context):
    """An organisation whose switch is on and that has a rule."""
    organisation = OrganisationHRSettingsFactory(
        registration_rules_enabled=True
    ).organisation
    RegistrationRuleFactory(organisation=organisation)
    return organisation


@pytest.mark.django_db
def test_saving_a_learner_queues_an_evaluation_of_the_learner(
    organisation_using_rules,
    database_task_backend,
    django_capture_on_commit_callbacks,
):
    # Arrange
    learner = LearnerFactory(organisation=organisation_using_rules)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.is_active = False
        learner.save()

    # Assert
    queued = _queued_tasks("evaluate_learner_task").get()
    assert queued.args_kwargs["args"] == [str(learner.pk), learner.site_id]


@pytest.mark.django_db
def test_saving_a_learner_field_no_rule_reads_queues_nothing_and_runs_no_query(
    organisation_using_rules,
    database_task_backend,
    django_capture_on_commit_callbacks,
):
    # Arrange
    learner = LearnerFactory(organisation=organisation_using_rules)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with (
        django_capture_on_commit_callbacks(execute=True),
        CaptureQueriesContext(connection) as queries,
    ):
        learner.save(update_fields=["user"])

    # Assert
    assert not _queued_tasks("evaluate_learner_task").exists()
    assert [q["sql"] for q in queries if "registration_rules" in q["sql"]] == []


@pytest.mark.django_db
def test_saving_learner_attributes_queues_an_evaluation_of_the_learner(
    organisation_using_rules,
    database_task_backend,
    django_capture_on_commit_callbacks,
):
    # Arrange
    attributes = LearnerHRAttributesFactory(
        learner__organisation=organisation_using_rules
    )
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        attributes.job_title = None
        attributes.save()

    # Assert
    queued = _queued_tasks("evaluate_learner_task").get()
    assert queued.args_kwargs["args"] == [
        str(attributes.learner_id),
        attributes.site_id,
    ]


@pytest.mark.django_db
def test_deleting_learner_attributes_queues_an_evaluation_of_the_learner(
    organisation_using_rules,
    database_task_backend,
    django_capture_on_commit_callbacks,
):
    # Arrange
    attributes = LearnerHRAttributesFactory(
        learner__organisation=organisation_using_rules
    )
    learner_id, site_id = attributes.learner_id, attributes.site_id
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        attributes.delete()

    # Assert
    queued = _queued_tasks("evaluate_learner_task").get()
    assert queued.args_kwargs["args"] == [str(learner_id), site_id]


@pytest.mark.django_db
def test_turning_the_switch_on_queues_an_evaluation_of_the_organisation(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    settings_row = OrganisationHRSettingsFactory(registration_rules_enabled=False)
    _queued_tasks("evaluate_organisation_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        settings_row.registration_rules_enabled = True
        settings_row.save()

    # Assert
    queued = _queued_tasks("evaluate_organisation_task").get()
    assert queued.args_kwargs["args"] == [
        str(settings_row.organisation_id),
        settings_row.site_id,
    ]


@pytest.mark.django_db
def test_saving_the_switch_off_queues_no_evaluation(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    settings_row = OrganisationHRSettingsFactory(registration_rules_enabled=True)
    _queued_tasks("evaluate_organisation_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        settings_row.registration_rules_enabled = False
        settings_row.save()

    # Assert
    assert not _queued_tasks("evaluate_organisation_task").exists()


@pytest.mark.django_db
def test_loading_a_learner_fixture_queues_nothing(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory()
    payload = serializers.serialize("json", [Learner._base_manager.get(pk=learner.pk)])
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        next(iter(serializers.deserialize("json", payload))).save()

    # Assert
    assert callbacks == []
    assert not _queued_tasks("evaluate_learner_task").exists()


@pytest.mark.django_db
def test_deleting_an_entry_a_rule_names_is_refused(mock_site_context):
    # Arrange
    entry = DepartmentFactory()
    conditions = AttributeRuleConditionsFactory(
        rule__organisation=entry.organisation, departments=[entry]
    )

    # Act
    with pytest.raises(ProtectedError), transaction.atomic():
        entry.delete()

    # Assert
    assert list(conditions.departments.all()) == [entry]


@pytest.mark.django_db
def test_an_entry_no_rule_names_can_be_deleted(mock_site_context):
    # Arrange
    entry = JobTitleFactory()
    AttributeRuleConditionsFactory(rule__organisation=entry.organisation)

    # Act
    entry.delete()

    # Assert
    assert not type(entry).objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_saving_a_learner_whose_organisation_has_rules_switched_off_queues_nothing(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    organisation = OrganisationHRSettingsFactory(
        registration_rules_enabled=False
    ).organisation
    RegistrationRuleFactory(organisation=organisation)
    learner = LearnerFactory(organisation=organisation)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.save()

    # Assert
    assert not _queued_tasks("evaluate_learner_task").exists()


@pytest.mark.django_db
def test_saving_a_learner_whose_organisation_has_no_rules_queues_nothing(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    organisation = OrganisationHRSettingsFactory(
        registration_rules_enabled=True
    ).organisation
    attributes = LearnerHRAttributesFactory(learner__organisation=organisation)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        attributes.learner.save()
        attributes.save()

    # Assert
    assert not _queued_tasks("evaluate_learner_task").exists()


@pytest.mark.django_db
def test_saving_a_learner_a_rule_registered_queues_an_evaluation_wherever_they_work(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    link = RuleRegistrationFactory()
    learner = Learner._base_manager.get(pk=link.registration.learner_id)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.save()

    # Assert
    assert _queued_tasks("evaluate_learner_task").count() == 1


@pytest.mark.django_db
def test_one_save_of_a_rule_and_its_pickers_queues_one_evaluation(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    conditions = AttributeRuleConditionsFactory()
    organisation = conditions.rule.organisation
    job_title = JobTitleFactory(organisation=organisation)
    department = DepartmentFactory(organisation=organisation)
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True), transaction.atomic():
        conditions.rule.save()
        conditions.save()
        conditions.job_titles.set([job_title])
        conditions.departments.set([department])
        conditions.locations.set([])

    # Assert
    assert _queued_tasks().count() == 1


@pytest.mark.django_db
def test_a_rolled_back_save_does_not_stop_a_later_one_queueing(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    rule = RegistrationRuleFactory()
    _queued_tasks().delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        with contextlib.suppress(RuntimeError), transaction.atomic():
            rule.save()
            raise RuntimeError
        rule.save()

    # Assert
    assert _queued_tasks().count() == 1


@pytest.mark.django_db
def test_changing_a_picker_outside_the_admin_marks_the_rule_changed(
    mock_site_context,
):
    # Arrange
    with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
        conditions = AttributeRuleConditionsFactory()
    entry = JobTitleFactory(organisation=conditions.rule.organisation)

    # Act
    with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
        conditions.job_titles.add(entry)

    # Assert
    rule = RegistrationRule._base_manager.get(pk=conditions.rule_id)
    assert rule.updated_at == datetime(2026, 2, 1, tzinfo=UTC)


@pytest.mark.django_db
def test_saving_conditions_outside_the_admin_marks_the_rule_changed(
    mock_site_context,
):
    # Arrange
    with time_machine.travel(datetime(2026, 1, 1, tzinfo=UTC), tick=False):
        conditions = AttributeRuleConditionsFactory()

    # Act
    with time_machine.travel(datetime(2026, 2, 1, tzinfo=UTC), tick=False):
        conditions.organisation_start_before = date(2025, 1, 1)
        conditions.save()

    # Assert
    rule = RegistrationRule._base_manager.get(pk=conditions.rule_id)
    assert rule.updated_at == datetime(2026, 2, 1, tzinfo=UTC)


@pytest.fixture
def rule_made_recommendation(mock_site_context):
    return RuleRecommendationFactory()


@pytest.mark.django_db
def test_registering_a_user_individually_deletes_a_rule_made_recommendation(
    rule_made_recommendation,
):
    # Arrange
    recommendation = rule_made_recommendation.recommendation
    learner = LearnerFactory(user=recommendation.user)

    # Act
    LearnerCourseRegistrationFactory(learner=learner, course=recommendation.course)

    # Assert
    assert not RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_registering_a_cohort_deletes_a_rule_made_recommendation_for_a_member(
    rule_made_recommendation,
):
    # Arrange
    recommendation = rule_made_recommendation.recommendation
    membership = CohortMembershipFactory(
        learner=LearnerFactory(user=recommendation.user)
    )

    # Act
    CohortCourseRegistrationFactory(
        cohort=membership.cohort, course=recommendation.course
    )

    # Assert
    assert not RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_joining_a_cohort_that_holds_the_course_deletes_a_rule_made_recommendation(
    rule_made_recommendation,
):
    # Arrange
    recommendation = rule_made_recommendation.recommendation
    cohort = CohortFactory()
    CohortCourseRegistrationFactory(cohort=cohort, course=recommendation.course)
    learner = LearnerFactory(user=recommendation.user, organisation=cohort.organisation)

    # Act
    CohortMembershipFactory(cohort=cohort, learner=learner)

    # Assert
    assert not RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_reactivating_a_learner_deletes_a_rule_made_recommendation(
    rule_made_recommendation,
):
    # Arrange
    recommendation = rule_made_recommendation.recommendation
    learner = LearnerFactory(user=recommendation.user, is_active=False)
    LearnerCourseRegistrationFactory(learner=learner, course=recommendation.course)
    learner = Learner._base_manager.get(pk=learner.pk)

    assert RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()

    # Act
    learner.is_active = True
    learner.save()

    # Assert
    assert not RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_reactivating_a_cohort_deletes_a_rule_made_recommendation_for_a_member(
    rule_made_recommendation,
):
    # Arrange
    recommendation = rule_made_recommendation.recommendation
    cohort = CohortFactory()
    Cohort._base_manager.filter(pk=cohort.pk).update(is_active=False)
    CohortCourseRegistrationFactory(cohort=cohort, course=recommendation.course)
    CohortMembershipFactory(
        cohort=cohort,
        learner=LearnerFactory(
            user=recommendation.user, organisation=cohort.organisation
        ),
    )
    cohort = Cohort._base_manager.get(pk=cohort.pk)

    assert RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()

    # Act
    cohort.is_active = True
    cohort.save()

    # Assert
    assert not RecommendedCourse._base_manager.filter(pk=recommendation.pk).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_saving_a_learner_in_an_organisation_without_rules_queues_an_evaluation_when_a_rule_holds_their_recommendation(
    mock_site_context, database_task_backend, django_capture_on_commit_callbacks
):
    # Arrange
    held = RuleRecommendationFactory()
    learner = LearnerFactory(user=held.recommendation.user)
    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.save()

    # Assert
    queued = _queued_tasks("evaluate_learner_task").get()
    assert queued.args_kwargs["args"] == [str(learner.pk), learner.site_id]


@pytest.mark.django_db
def test_deactivating_a_learner_in_the_admin_removes_the_rules_recommendation_once_the_task_runs(
    staff_client, mock_site_context, database_task_backend
):
    # Arrange
    rule = RegistrationRuleFactory(
        is_enabled=True, outcome=RegistrationRule.Outcome.RECOMMEND
    )
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=True
    )
    learner = LearnerFactory(organisation=rule.organisation)
    RuleRecommendationFactory(
        rule=rule,
        recommendation=RecommendedCourseFactory(user=learner.user, course=rule.course),
    )
    url = reverse(
        "admin:freedom_ls_learner_management_learner_change", args=[learner.pk]
    )
    payload = _admin_form_post(staff_client.get(url), is_active=False)

    # Act
    staff_client.post(url, payload)
    evaluate_learner_task.func(str(learner.pk), learner.site_id)

    # Assert
    assert not RecommendedCourse._base_manager.filter(user=learner.user).exists()
    assert not RuleRecommendation._base_manager.exists()


@pytest.fixture
def recommend_rule(mock_site_context):
    rule = RegistrationRuleFactory(
        is_enabled=True, outcome=RegistrationRule.Outcome.RECOMMEND
    )
    OrganisationHRSettingsFactory(
        organisation=rule.organisation, registration_rules_enabled=True
    )
    return rule


@pytest.fixture
def registered_learner(recommend_rule):
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    LearnerCourseRegistrationFactory(learner=learner, course=recommend_rule.course)
    return learner


@pytest.fixture
def cohort_holding_the_course(recommend_rule):
    cohort = CohortFactory(organisation=recommend_rule.organisation)
    CohortCourseRegistrationFactory(cohort=cohort, course=recommend_rule.course)
    return cohort


def _is_recommended(rule, user) -> bool:
    return RecommendedCourse._base_manager.filter(
        user=user, course=rule.course
    ).exists()


@pytest.mark.django_db
def test_deactivating_a_registration_recommends_the_course_again(
    recommend_rule, registered_learner, django_capture_on_commit_callbacks
):
    # Arrange
    registration = LearnerCourseRegistration._base_manager.get(
        learner=registered_learner
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.is_active = False
        registration.save()

    # Assert
    assert _is_recommended(recommend_rule, registered_learner.user)


@pytest.mark.django_db
def test_deleting_a_registration_recommends_the_course_again(
    recommend_rule, registered_learner, django_capture_on_commit_callbacks
):
    # Arrange
    registration = LearnerCourseRegistration._base_manager.get(
        learner=registered_learner
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.delete()

    # Assert
    assert _is_recommended(recommend_rule, registered_learner.user)


@pytest.mark.django_db
def test_deleting_a_membership_recommends_the_cohorts_course_again(
    recommend_rule, cohort_holding_the_course, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    membership = CohortMembershipFactory(
        cohort=cohort_holding_the_course, learner=learner
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        membership.delete()

    # Assert
    assert _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_deactivating_a_learner_recommends_the_course_through_the_users_other_learner(
    recommend_rule, django_capture_on_commit_callbacks
):
    # Arrange
    user_learner = LearnerFactory(organisation=recommend_rule.organisation)
    registering_learner = LearnerFactory(
        user=user_learner.user, organisation=OrganisationFactory()
    )
    LearnerCourseRegistrationFactory(
        learner=registering_learner, course=recommend_rule.course
    )
    registering_learner = Learner._base_manager.get(pk=registering_learner.pk)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registering_learner.is_active = False
        registering_learner.save()

    # Assert
    assert _is_recommended(recommend_rule, user_learner.user)


@pytest.mark.django_db
def test_deleting_a_learner_recommends_the_course_through_the_users_other_learner(
    recommend_rule, django_capture_on_commit_callbacks
):
    # Arrange
    user_learner = LearnerFactory(organisation=recommend_rule.organisation)
    registering_learner = LearnerFactory(
        user=user_learner.user, organisation=OrganisationFactory()
    )
    LearnerCourseRegistrationFactory(
        learner=registering_learner, course=recommend_rule.course
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registering_learner.delete()

    # Assert
    assert _is_recommended(recommend_rule, user_learner.user)


@pytest.mark.django_db
def test_deleting_a_users_only_learner_removes_the_rules_recommendation(
    recommend_rule, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    RuleRecommendationFactory(
        rule=recommend_rule,
        recommendation=RecommendedCourseFactory(
            user=learner.user, course=recommend_rule.course
        ),
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.delete()

    # Assert
    assert not _is_recommended(recommend_rule, learner.user)
    assert not RuleRecommendation._base_manager.exists()


@pytest.mark.django_db
def test_deactivating_a_users_only_learner_removes_the_rules_recommendation(
    recommend_rule, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    RuleRecommendationFactory(
        rule=recommend_rule,
        recommendation=RecommendedCourseFactory(
            user=learner.user, course=recommend_rule.course
        ),
    )
    learner = Learner._base_manager.get(pk=learner.pk)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        learner.is_active = False
        learner.save()

    # Assert
    assert not _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_deactivating_a_cohort_registration_recommends_the_course_to_members_again(
    recommend_rule, cohort_holding_the_course, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    CohortMembershipFactory(cohort=cohort_holding_the_course, learner=learner)
    registration = CohortCourseRegistration._base_manager.get(
        cohort=cohort_holding_the_course
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.is_active = False
        registration.save()

    # Assert
    assert _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_deleting_a_cohort_registration_recommends_the_course_to_members_again(
    recommend_rule, cohort_holding_the_course, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    CohortMembershipFactory(cohort=cohort_holding_the_course, learner=learner)
    registration = CohortCourseRegistration._base_manager.get(
        cohort=cohort_holding_the_course
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.delete()

    # Assert
    assert _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_deactivating_a_cohort_recommends_its_course_to_members_again(
    recommend_rule, cohort_holding_the_course, django_capture_on_commit_callbacks
):
    # Arrange
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    CohortMembershipFactory(cohort=cohort_holding_the_course, learner=learner)
    cohort = Cohort._base_manager.get(pk=cohort_holding_the_course.pk)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        cohort.is_active = False
        cohort.save()

    # Assert
    assert _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_deleting_a_cohort_recommends_its_course_only_to_members_registered_no_other_way(
    recommend_rule, cohort_holding_the_course, django_capture_on_commit_callbacks
):
    # Arrange
    only_member = LearnerFactory(organisation=recommend_rule.organisation)
    also_registered = LearnerFactory(organisation=recommend_rule.organisation)
    CohortMembershipFactory(cohort=cohort_holding_the_course, learner=only_member)
    CohortMembershipFactory(cohort=cohort_holding_the_course, learner=also_registered)
    LearnerCourseRegistrationFactory(
        learner=also_registered, course=recommend_rule.course
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        cohort_holding_the_course.delete()

    # Assert
    assert _is_recommended(recommend_rule, only_member.user)
    assert not _is_recommended(recommend_rule, also_registered.user)


@pytest.mark.django_db
def test_a_withdrawn_registration_does_not_recommend_to_a_user_registered_another_way(
    recommend_rule,
    registered_learner,
    cohort_holding_the_course,
    django_capture_on_commit_callbacks,
):
    # Arrange
    CohortMembershipFactory(
        cohort=cohort_holding_the_course, learner=registered_learner
    )
    registration = LearnerCourseRegistration._base_manager.get(
        learner=registered_learner
    )
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.is_active = False
        registration.save()

    # Assert
    assert not _is_recommended(recommend_rule, registered_learner.user)


@pytest.mark.django_db
def test_a_register_rule_retracting_a_learner_recommends_the_course_again(
    recommend_rule, django_capture_on_commit_callbacks
):
    # Arrange
    job_title = JobTitleFactory(organisation=recommend_rule.organisation)
    register_rule = RegistrationRuleFactory(
        organisation=recommend_rule.organisation,
        course=recommend_rule.course,
        is_enabled=True,
    )
    AttributeRuleConditionsFactory(rule=register_rule, job_titles=[job_title])
    learner = LearnerFactory(organisation=recommend_rule.organisation)
    registration = LearnerCourseRegistrationFactory(
        learner=learner, course=recommend_rule.course, self_registered=False
    )
    RuleRegistrationFactory(rule=register_rule, registration=registration)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_rule(register_rule.pk, register_rule.site_id)

    # Assert
    assert _is_recommended(recommend_rule, learner.user)


@pytest.mark.django_db
def test_withdrawing_a_registration_with_the_switch_off_queues_nothing(
    recommend_rule,
    registered_learner,
    database_task_backend,
    django_capture_on_commit_callbacks,
):
    # Arrange
    OrganisationHRSettings._base_manager.filter(
        organisation=recommend_rule.organisation
    ).update(registration_rules_enabled=False)
    registration = LearnerCourseRegistration._base_manager.get(
        learner=registered_learner
    )

    _queued_tasks("evaluate_learner_task").delete()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        registration.is_active = False
        registration.save()

    # Assert
    assert not _queued_tasks("evaluate_learner_task").exists()
    assert not _is_recommended(recommend_rule, registered_learner.user)


@pytest.mark.django_db
def test_turning_the_switch_on_recommends_to_users_withdrawn_while_it_was_off(
    recommend_rule, registered_learner, django_capture_on_commit_callbacks
):
    # Arrange
    OrganisationHRSettings._base_manager.filter(
        organisation=recommend_rule.organisation
    ).update(registration_rules_enabled=False)
    registration = LearnerCourseRegistration._base_manager.get(
        learner=registered_learner
    )
    registration.is_active = False
    registration.save()
    OrganisationHRSettings._base_manager.filter(
        organisation=recommend_rule.organisation
    ).update(registration_rules_enabled=True)
    drop_ambient_request()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        evaluate_organisation(recommend_rule.organisation_id, recommend_rule.site_id)

    # Assert
    assert _is_recommended(recommend_rule, registered_learner.user)


@pytest.mark.django_db
def test_loading_a_deactivated_registration_fixture_queues_nothing(
    recommend_rule, registered_learner, django_capture_on_commit_callbacks
):
    # Arrange
    LearnerCourseRegistration._base_manager.filter(learner=registered_learner).update(
        is_active=False
    )
    payload = serializers.serialize(
        "json",
        [LearnerCourseRegistration._base_manager.get(learner=registered_learner)],
    )

    # Act
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        next(iter(serializers.deserialize("json", payload))).save()

    # Assert
    assert callbacks == []


@pytest.mark.django_db
def test_deleting_a_rule_deletes_the_recommendations_it_alone_held(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(outcome=RegistrationRule.Outcome.RECOMMEND)
    sole = RuleRecommendationFactory(rule=rule)

    # Act
    rule.delete()

    # Assert
    assert not RecommendedCourse._base_manager.filter(
        pk=sole.recommendation_id
    ).exists()


@pytest.mark.django_db
def test_deleting_a_rule_leaves_a_recommendation_another_rule_holds(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(outcome=RegistrationRule.Outcome.RECOMMEND)
    shared = RuleRecommendationFactory(rule=rule)
    other = RuleRecommendationFactory(
        recommendation=shared.recommendation,
        rule=RegistrationRuleFactory(outcome=RegistrationRule.Outcome.RECOMMEND),
    )

    # Act
    rule.delete()

    # Assert
    assert RecommendedCourse._base_manager.filter(pk=shared.recommendation_id).exists()
    assert RuleRecommendation._base_manager.filter(pk=other.pk).exists()
    assert not RuleRecommendation._base_manager.filter(pk=shared.pk).exists()


@pytest.mark.django_db
def test_deleting_a_rule_leaves_staff_made_recommendations(mock_site_context):
    # Arrange
    rule = RegistrationRuleFactory(outcome=RegistrationRule.Outcome.RECOMMEND)
    RuleRecommendationFactory(rule=rule)
    staff_made = RecommendedCourseFactory()

    # Act
    rule.delete()

    # Assert
    assert RecommendedCourse._base_manager.filter(pk=staff_made.pk).exists()
