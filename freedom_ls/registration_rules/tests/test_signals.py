"""Tests for the registration rule signal receivers."""

from __future__ import annotations

import contextlib
from datetime import UTC, date, datetime

import pytest
import time_machine

from django.core import serializers
from django.db import transaction
from django.db.models import ProtectedError
from django.urls import reverse

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    OrganisationHRSettingsFactory,
)
from freedom_ls.learner_management.factories import (
    LearnerCourseRegistrationFactory,
    LearnerFactory,
)
from freedom_ls.learner_management.models import Learner, LearnerCourseRegistration
from freedom_ls.organisations.utils import get_default_organisation
from freedom_ls.registration_rules.evaluation import evaluate_rule
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration
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


def _registration_form_post(response, *, is_active: bool) -> dict[str, str]:
    """The registration change form's own values, with is_active set."""
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
    payload = _registration_form_post(staff_client.get(url), is_active=is_active)

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
    payload = _registration_form_post(staff_client.get(url), is_active=True)

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
