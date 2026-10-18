"""Tests for the registration rule admin."""

from __future__ import annotations

import re

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import DepartmentFactory, JobTitleFactory
from freedom_ls.registration_rules.factories import (
    AttributeRuleConditionsFactory,
    RegistrationRuleFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRegistration,
)


@pytest.mark.django_db
def test_add_page_offers_only_name_organisation_and_course(staff_client):
    # Act
    response = staff_client.get(
        reverse("admin:freedom_ls_registration_rules_registrationrule_add")
    )

    # Assert
    assert response.status_code == 200
    assert list(response.context["adminform"].form.fields) == [
        "name",
        "organisation",
        "course",
    ]
    assert response.context["inline_admin_formsets"] == []


@pytest.mark.django_db
def test_saving_a_new_rule_lands_on_its_change_page_disabled(staff_client):
    # Arrange
    organisation = OrganisationFactory()
    course = CourseFactory()

    # Act
    response = staff_client.post(
        reverse("admin:freedom_ls_registration_rules_registrationrule_add"),
        {"name": "Finance", "organisation": organisation.pk, "course": course.pk},
    )

    # Assert
    rule = RegistrationRule.objects.get(name="Finance")
    assert response.status_code == 302
    assert response.url == reverse(
        "admin:freedom_ls_registration_rules_registrationrule_change", args=[rule.pk]
    )
    assert rule.is_enabled is False


@pytest.mark.django_db
def test_organisation_and_course_are_read_only_on_the_change_page(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()

    # Act
    response = staff_client.get(
        reverse(
            "admin:freedom_ls_registration_rules_registrationrule_change",
            args=[rule.pk],
        )
    )

    # Assert
    assert response.status_code == 200
    editable = response.context["adminform"].form.fields
    assert "organisation" not in editable
    assert "course" not in editable
    assert "is_enabled" in editable


REGISTRATION_CHANGE = (
    "admin:freedom_ls_learner_management_learnercourseregistration_change"
)
RULE_CHANGE = "admin:freedom_ls_registration_rules_registrationrule_change"
RULE_DELETE = "admin:freedom_ls_registration_rules_registrationrule_delete"
RULE_CHANGELIST = "admin:freedom_ls_registration_rules_registrationrule_changelist"


@pytest.mark.django_db
def test_a_rule_made_registration_shows_its_rule_as_a_link(staff_client):
    # Arrange
    link = RuleRegistrationFactory()

    # Act
    response = staff_client.get(
        reverse(REGISTRATION_CHANGE, args=[link.registration.pk])
    )

    # Assert
    assert response.status_code == 200
    assert "registration_rule" in response.context["adminform"].readonly_fields
    assert (
        f'<a href="{reverse(RULE_CHANGE, args=[link.rule.pk])}">{link.rule.name}</a>'
        in response.content.decode()
    )


@pytest.mark.django_db
def test_a_staff_made_registration_shows_no_rule(staff_client):
    # Arrange
    registration = LearnerCourseRegistrationFactory()

    # Act
    response = staff_client.get(reverse(REGISTRATION_CHANGE, args=[registration.pk]))

    # Assert
    assert response.status_code == 200
    assert "Registration rule" in response.content.decode()
    assert not re.search(
        r"registrationrule/[0-9a-f-]{36}/change", response.content.decode()
    )


@pytest.mark.django_db
def test_a_registration_whose_rule_was_deleted_says_so(staff_client):
    # Arrange
    link = RuleRegistrationFactory(rule__is_enabled=False)
    rule_name = link.rule.name
    link.rule.delete()

    # Act
    response = staff_client.get(
        reverse(REGISTRATION_CHANGE, args=[link.registration.pk])
    )

    # Assert
    assert f"{rule_name} (deleted)" in response.content.decode()


@pytest.mark.django_db
def test_an_enabled_rule_cannot_be_deleted(staff_client):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)

    # Act
    response = staff_client.post(reverse(RULE_DELETE, args=[rule.pk]), {"post": "yes"})

    # Assert
    assert response.status_code == 403
    assert RegistrationRule.objects.filter(pk=rule.pk).exists()


@pytest.mark.django_db
def test_a_disabled_rule_can_be_deleted(staff_client):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=False)

    # Act
    response = staff_client.post(reverse(RULE_DELETE, args=[rule.pk]), {"post": "yes"})

    # Assert
    assert response.status_code == 302
    assert not RegistrationRule.objects.filter(pk=rule.pk).exists()


@pytest.mark.django_db
def test_deleting_a_disabled_rule_leaves_its_registrations_with_its_name(staff_client):
    # Arrange
    link = RuleRegistrationFactory(rule__is_enabled=False)
    rule_name = link.rule.name

    # Act
    staff_client.post(reverse(RULE_DELETE, args=[link.rule.pk]), {"post": "yes"})

    # Assert
    link = RuleRegistration.objects.get(pk=link.pk)
    assert link.rule is None
    assert link.rule_name == rule_name


@pytest.mark.django_db
def test_bulk_delete_confirmation_names_an_enabled_rule_as_protected(staff_client):
    # Arrange
    enabled = RegistrationRuleFactory(is_enabled=True)
    disabled = RegistrationRuleFactory(is_enabled=False)

    # Act
    response = staff_client.post(
        reverse(RULE_CHANGELIST),
        {
            "action": "delete_selected",
            "_selected_action": [str(enabled.pk), str(disabled.pk)],
        },
    )

    # Assert
    assert response.status_code == 200
    assert response.context["protected"] == [f"Enabled rule: {enabled.name}"]


def _picker_field(response, name: str):
    """A picker field of the conditions inline on a change page."""
    return response.context["inline_admin_formsets"][0].formset.forms[0].fields[name]


def _conditions_post(rule: RegistrationRule, **inline: object) -> dict[str, object]:
    """A change-page POST that adds the conditions row, as the browser sends it."""
    data: dict[str, object] = {
        "name": rule.name,
        "attribute_conditions-TOTAL_FORMS": "1",
        "attribute_conditions-INITIAL_FORMS": "0",
        "attribute_conditions-MIN_NUM_FORMS": "0",
        "attribute_conditions-MAX_NUM_FORMS": "1",
    }
    data.update(
        {f"attribute_conditions-0-{key}": value for key, value in inline.items()}
    )
    return data


def _change_page(client, rule: RegistrationRule):
    return client.get(reverse(RULE_CHANGE, args=[rule.pk]))


@pytest.mark.django_db
def test_the_change_page_offers_the_organisations_active_entries(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    active = JobTitleFactory(organisation=rule.organisation)
    JobTitleFactory(organisation=rule.organisation, is_active=False)
    JobTitleFactory()

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert list(_picker_field(response, "job_titles").queryset) == [active]


@pytest.mark.django_db
def test_the_change_page_keeps_an_inactive_entry_the_rule_holds(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    held = JobTitleFactory(organisation=rule.organisation, is_active=False)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[held])

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert held in _picker_field(response, "job_titles").queryset


@pytest.mark.django_db
def test_a_held_inactive_entry_is_labelled_inactive(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    held = JobTitleFactory(organisation=rule.organisation, is_active=False)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[held])

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    labels = [label for _, label in _picker_field(response, "job_titles").choices]
    assert labels == [f"{held.name} (inactive)"]


@pytest.mark.django_db
def test_an_entry_of_another_organisation_is_refused_on_its_picker(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    foreign = JobTitleFactory()

    # Act
    response = staff_client.post(
        reverse(RULE_CHANGE, args=[rule.pk]),
        _conditions_post(rule, job_titles=[foreign.pk]),
    )

    # Assert
    errors = response.context["inline_admin_formsets"][0].formset.errors[0]
    assert errors["job_titles"] == ["Choose entries from this rule's organisation."]


@pytest.mark.django_db
def test_an_entry_of_another_organisation_is_not_saved(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    foreign = JobTitleFactory()

    # Act
    staff_client.post(
        reverse(RULE_CHANGE, args=[rule.pk]),
        _conditions_post(rule, job_titles=[foreign.pk]),
    )

    # Assert
    assert not AttributeRuleConditions.objects.filter(rule=rule).exists()


@pytest.mark.django_db
def test_posting_an_organisations_entry_saves_it_on_the_rule(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    entry = DepartmentFactory(organisation=rule.organisation)

    # Act
    staff_client.post(
        reverse(RULE_CHANGE, args=[rule.pk]),
        _conditions_post(rule, departments=[entry.pk]),
    )

    # Assert
    assert list(rule.attribute_conditions.departments.all()) == [entry]


@pytest.mark.django_db
def test_saving_the_inline_queues_an_evaluation_of_the_rule(
    staff_client, settings, django_capture_on_commit_callbacks
):
    # Arrange
    settings.TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}
    rule = RegistrationRuleFactory()

    # Act
    with django_capture_on_commit_callbacks(execute=True):
        staff_client.post(reverse(RULE_CHANGE, args=[rule.pk]), _conditions_post(rule))

    # Assert
    from django_tasks_db.models import DBTaskResult

    queued = DBTaskResult.objects.filter(
        task_path="freedom_ls.registration_rules.tasks.evaluate_rule_task"
    )
    assert {task.args_kwargs["args"][0] for task in queued} == {str(rule.pk)}


@pytest.mark.django_db
def test_each_rule_is_offered_only_its_own_organisations_entries(staff_client):
    # Arrange
    first_rule, second_rule = RegistrationRuleFactory.create_batch(2)
    first_entry = JobTitleFactory(organisation=first_rule.organisation)
    second_entry = JobTitleFactory(organisation=second_rule.organisation)

    # Act
    first_page = _change_page(staff_client, first_rule)
    second_page = _change_page(staff_client, second_rule)

    # Assert
    assert list(_picker_field(first_page, "job_titles").queryset) == [first_entry]
    assert list(_picker_field(second_page, "job_titles").queryset) == [second_entry]


@pytest.mark.django_db
def test_the_change_page_warns_about_a_held_inactive_entry(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    held = JobTitleFactory(organisation=rule.organisation, is_active=False)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[held])

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    warnings = [str(message) for message in response.context["messages"]]
    assert any(f"{held.name} (job title)" in warning for warning in warnings)


@pytest.mark.django_db
def test_the_change_page_does_not_warn_when_every_held_entry_is_active(staff_client):
    # Arrange
    rule = RegistrationRuleFactory()
    held = JobTitleFactory(organisation=rule.organisation)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[held])

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert list(response.context["messages"]) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    (
        "is_active",
        "expected",
    ),
    [(False, True), (True, False)],
)
def test_the_changelist_flags_a_rule_that_uses_an_inactive_entry(
    staff_client, is_active, expected
):
    # Arrange
    rule = RegistrationRuleFactory()
    entry = JobTitleFactory(organisation=rule.organisation, is_active=is_active)
    AttributeRuleConditionsFactory(rule=rule, job_titles=[entry])

    # Act
    response = staff_client.get(reverse(RULE_CHANGELIST))

    # Assert
    (listed,) = response.context["cl"].result_list
    assert listed.uses_inactive_entries is expected
