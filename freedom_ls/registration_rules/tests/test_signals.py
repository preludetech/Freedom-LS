"""Tests for the registration rule signal receivers."""

from __future__ import annotations

from datetime import date

import pytest

from django.core import serializers

from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import JobTitleFactory
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration


@pytest.fixture
def database_task_backend(settings) -> None:
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}


def _queued_tasks():
    from django_tasks_db.models import DBTaskResult

    return DBTaskResult.objects.filter(
        task_path="freedom_ls.registration_rules.tasks.evaluate_rule_task"
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
