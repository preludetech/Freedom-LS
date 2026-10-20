"""Tests for the registration rule admin."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import time_machine

from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.learner_management.factories import LearnerCourseRegistrationFactory
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.learner_progress.factories import CourseProgressFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed
from freedom_ls.tests.site_context import drop_ambient_request

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    OrganisationHRSettingsFactory,
)
from freedom_ls.hr_attributes.models import JobTitle
from freedom_ls.registration_rules.evaluation import evaluate_rule
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
from freedom_ls.registration_rules.tests.helpers import change_payload


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


JOB_TITLE_DELETE = "admin:freedom_ls_hr_attributes_jobtitle_delete"


@pytest.mark.django_db
def test_the_delete_page_of_an_entry_a_rule_names_lists_the_rule_as_protected(
    staff_client,
):
    # Arrange
    entry = JobTitleFactory()
    conditions = AttributeRuleConditionsFactory(
        rule__organisation=entry.organisation, job_titles=[entry]
    )

    # Act
    response = staff_client.get(reverse(JOB_TITLE_DELETE, args=[entry.pk]))

    # Assert
    assert response.status_code == 200
    assert response.context["protected"] == [
        f"Registration rule: {conditions.rule.name}"
    ]


@pytest.mark.django_db
def test_an_entry_a_rule_names_is_not_deleted_from_the_admin(staff_client):
    # Arrange
    entry = JobTitleFactory()
    AttributeRuleConditionsFactory(
        rule__organisation=entry.organisation, job_titles=[entry]
    )

    # Act
    staff_client.post(reverse(JOB_TITLE_DELETE, args=[entry.pk]), {"post": "yes"})

    # Assert
    assert JobTitle.objects.filter(pk=entry.pk).exists()


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


@pytest.fixture
def rules_on(mock_site_context):
    """An organisation whose registration rules switch is on."""
    return OrganisationHRSettingsFactory(registration_rules_enabled=True).organisation


@pytest.fixture
def department(rules_on):
    return DepartmentFactory(organisation=rules_on)


def _learner_in(organisation, **attributes):
    return LearnerHRAttributesFactory(
        learner__organisation=organisation, **attributes
    ).learner


def _make_rule_registration(rule, learner, *, is_active=True, is_retracted=False):
    registration = LearnerCourseRegistrationFactory(
        learner=learner,
        course=rule.course,
        is_active=is_active,
        self_registered=False,
    )
    RuleRegistrationFactory(
        rule=rule, registration=registration, is_retracted=is_retracted
    )
    return registration


def _active_learner_ids(course) -> set:
    return set(
        LearnerCourseRegistration._base_manager.filter(
            course=course, is_active=True
        ).values_list("learner_id", flat=True)
    )


def _listed_ids(response, key: str) -> set:
    return {learner.pk for learner in response.context[key]}


def _post_change(client, rule, **kwargs):
    return client.post(
        reverse(RULE_CHANGE, args=[rule.pk]), change_payload(rule, **kwargs)
    )


def _confirm(client, rule, capture, **kwargs):
    with capture(execute=True):
        return client.post(
            reverse(RULE_CHANGE, args=[rule.pk]),
            {**change_payload(rule, **kwargs), "_confirmed": "1"},
        )


@pytest.mark.django_db
def test_enabling_a_rule_previews_the_learners_it_would_register(
    staff_client, rules_on, department
):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on)
    learner = _learner_in(rules_on, department=department)
    _learner_in(rules_on)

    # Act
    response = _post_change(
        staff_client, rule, is_enabled=True, departments=[department.pk]
    )

    # Assert
    assert response.status_code == 200
    assert response.templates[0].name == "admin/registration_rules/preview.html"
    assert _listed_ids(response, "will_register") == {learner.pk}


@pytest.mark.django_db
def test_previewing_an_enable_saves_nothing(staff_client, rules_on, department):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on)
    _learner_in(rules_on, department=department)

    # Act
    _post_change(staff_client, rule, is_enabled=True, departments=[department.pk])

    # Assert
    rule.refresh_from_db()
    assert rule.is_enabled is False
    assert not AttributeRuleConditions.objects.filter(rule=rule).exists()
    assert not LearnerCourseRegistration._base_manager.filter(
        course=rule.course
    ).exists()


@pytest.fixture
def edited_rule(rules_on, department):
    """An enabled rule on `department`, with one learner it made and one it will gain."""
    other = DepartmentFactory(organisation=rules_on)
    rule = RegistrationRuleFactory(organisation=rules_on, is_enabled=True)
    AttributeRuleConditionsFactory(rule=rule, departments=[department])
    held = _learner_in(rules_on, department=department)
    _make_rule_registration(rule, held)
    gained = _learner_in(rules_on, department=other)
    retracted = _learner_in(rules_on, department=other)
    _make_rule_registration(rule, retracted, is_active=False, is_retracted=True)
    return SimpleNamespace(
        rule=rule,
        other=other,
        held=held,
        gained=gained,
        retracted=retracted,
    )


@pytest.mark.django_db
def test_editing_an_enabled_rule_lists_the_learners_it_would_register(
    staff_client, edited_rule
):
    # Act
    response = _post_change(
        staff_client,
        edited_rule.rule,
        is_enabled=True,
        departments=[edited_rule.other.pk],
    )

    # Assert
    assert _listed_ids(response, "will_register") == {
        edited_rule.gained.pk,
        edited_rule.retracted.pk,
    }


@pytest.mark.django_db
def test_editing_an_enabled_rule_lists_the_learners_it_would_retract(
    staff_client, edited_rule
):
    # Act
    response = _post_change(
        staff_client,
        edited_rule.rule,
        is_enabled=True,
        departments=[edited_rule.other.pk],
    )

    # Assert
    assert _listed_ids(response, "will_retract") == {edited_rule.held.pk}


@pytest.mark.django_db
def test_disabling_a_rule_lists_the_learners_it_would_retract(
    staff_client, edited_rule
):
    # Act
    response = _post_change(staff_client, edited_rule.rule, is_enabled=False)

    # Assert
    assert _listed_ids(response, "will_retract") == {edited_rule.held.pk}


@pytest.mark.django_db
def test_a_learner_who_started_the_course_stays_registered_with_that_reason(
    staff_client, edited_rule
):
    # Arrange
    registration = LearnerCourseRegistration._base_manager.get(learner=edited_rule.held)
    CourseProgressFactory(
        learner=edited_rule.held,
        course=edited_rule.rule.course,
        learner_registration=registration,
        progress_percentage=10,
    )

    # Act
    response = _post_change(
        staff_client,
        edited_rule.rule,
        is_enabled=True,
        departments=[edited_rule.other.pk],
    )

    # Assert
    assert response.context["stays_registered"] == [
        (edited_rule.held, "Started the course")
    ]
    assert _listed_ids(response, "will_retract") == set()


@pytest.mark.django_db
def test_a_learner_another_enabled_rule_holds_stays_registered_with_its_name(
    staff_client, edited_rule, department
):
    # Arrange
    taker = RegistrationRuleFactory(
        organisation=edited_rule.rule.organisation,
        course=edited_rule.rule.course,
        is_enabled=True,
    )
    AttributeRuleConditionsFactory(rule=taker, departments=[department])

    # Act
    response = _post_change(
        staff_client,
        edited_rule.rule,
        is_enabled=True,
        departments=[edited_rule.other.pk],
    )

    # Assert
    assert response.context["stays_registered"] == [
        (edited_rule.held, f"Still matched by {taker.name}")
    ]


@pytest.mark.django_db
def test_confirming_an_enable_registers_the_learners_the_preview_named(
    staff_client, rules_on, department, django_capture_on_commit_callbacks
):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on)
    _learner_in(rules_on, department=department)
    _learner_in(rules_on)
    payload = {"is_enabled": True, "departments": [department.pk]}
    preview = _post_change(staff_client, rule, **payload)

    # Act
    _confirm(staff_client, rule, django_capture_on_commit_callbacks, **payload)

    # Assert
    assert _active_learner_ids(rule.course) == _listed_ids(preview, "will_register")


@pytest.mark.django_db
def test_confirming_an_edit_leaves_the_registrations_the_preview_described(
    staff_client, edited_rule, django_capture_on_commit_callbacks
):
    # Arrange
    payload = {"is_enabled": True, "departments": [edited_rule.other.pk]}
    preview = _post_change(staff_client, edited_rule.rule, **payload)
    expected = (
        _active_learner_ids(edited_rule.rule.course)
        | _listed_ids(preview, "will_register")
    ) - _listed_ids(preview, "will_retract")

    # Act
    _confirm(
        staff_client,
        edited_rule.rule,
        django_capture_on_commit_callbacks,
        **payload,
    )

    # Assert
    assert _active_learner_ids(edited_rule.rule.course) == expected


@pytest.mark.django_db
def test_confirming_a_disable_retracts_the_learners_the_preview_named(
    staff_client, edited_rule, django_capture_on_commit_callbacks
):
    # Arrange
    preview = _post_change(staff_client, edited_rule.rule, is_enabled=False)

    # Act
    _confirm(
        staff_client,
        edited_rule.rule,
        django_capture_on_commit_callbacks,
        is_enabled=False,
    )

    # Assert
    assert _active_learner_ids(edited_rule.rule.course) == set()
    assert _listed_ids(preview, "will_retract") == {edited_rule.held.pk}


@pytest.mark.django_db
def test_saving_a_rule_that_stays_disabled_skips_the_preview(staff_client, rules_on):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on)

    # Act
    response = _post_change(staff_client, rule)

    # Assert
    assert response.status_code == 302
    assert response.url == reverse(RULE_CHANGELIST)


@pytest.mark.django_db
def test_the_preview_says_nothing_changes_while_the_switch_is_off(
    staff_client, mock_site_context
):
    # Arrange
    rule = RegistrationRuleFactory()

    # Act
    response = _post_change(staff_client, rule, is_enabled=True)

    # Assert
    assert response.context["switch_is_off"] is True


@pytest.mark.django_db
def test_the_preview_still_lists_learners_while_the_switch_is_off(
    staff_client, mock_site_context
):
    # Arrange
    rule = RegistrationRuleFactory()
    learner = _learner_in(rule.organisation)

    # Act
    response = _post_change(staff_client, rule, is_enabled=True)

    # Assert
    assert _listed_ids(response, "will_register") == {learner.pk}


@pytest.fixture
def rule_changer_client(mock_site_context, logged_in_client):
    """A staff user who may change rules but not look at learners."""
    user = UserFactory(staff=True)
    user.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="freedom_ls_registration_rules"
        )
    )
    return logged_in_client(user)


@pytest.mark.django_db
def test_a_user_without_view_learner_permission_sees_counts_and_no_names(
    rule_changer_client, rules_on
):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on)
    learner = _learner_in(rules_on)

    # Act
    response = _post_change(rule_changer_client, rule, is_enabled=True)

    # Assert
    content = response.content.decode()
    assert "Will be registered (1)" in content
    assert learner.user.email not in content


@pytest.mark.django_db
def test_a_user_with_view_permission_only_cannot_post_a_change(
    mock_site_context, logged_in_client
):
    # Arrange
    user = UserFactory(staff=True)
    user.user_permissions.set(
        Permission.objects.filter(codename="view_registrationrule")
    )
    rule = RegistrationRuleFactory()

    # Act
    response = _post_change(logged_in_client(user), rule, is_enabled=True)

    # Assert
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_change_posted_without_a_csrf_token_is_refused(mock_site_context):
    # Arrange
    client = Client(enforce_csrf_checks=True)
    client.force_login(UserFactory(superuser=True))
    rule = RegistrationRuleFactory()

    # Act
    response = _post_change(client, rule, is_enabled=True)

    # Assert
    assert response.status_code == 403


@pytest.fixture
def preview_inputs(staff_client, rules_on, department) -> list[str]:
    rule = RegistrationRuleFactory(organisation=rules_on)
    response = _post_change(
        staff_client, rule, is_enabled=True, departments=[department.pk]
    )
    # The admin shell has its own forms; only the confirmation form counts.
    (confirm_form,) = [
        form
        for form in re.findall(r"<form.*?</form>", response.content.decode(), re.DOTALL)
        if "_confirmed" in form
    ]
    return re.findall(r'<input type="hidden" name="([^"]+)"', confirm_form)


@pytest.mark.django_db
def test_the_preview_posts_back_the_inline_management_form(preview_inputs):
    assert "attribute_conditions-TOTAL_FORMS" in preview_inputs


@pytest.mark.django_db
def test_the_preview_carries_one_csrf_token(preview_inputs):
    assert preview_inputs.count("csrfmiddlewaretoken") == 1


_FEB = datetime(2026, 2, 1, tzinfo=UTC)


def _warnings(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def _flag_for(client, rule) -> bool:
    response = client.get(reverse(RULE_CHANGELIST))
    (listed,) = response.context["cl"].result_list
    assert listed.pk == rule.pk
    return bool(listed.change_not_yet_applied)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("is_enabled", "last_evaluated_at", "expected"),
    [
        (False, None, False),
        (True, None, True),
        (True, _FEB - timedelta(days=1), True),
        (True, _FEB + timedelta(days=1), False),
    ],
    ids=[
        "disabled",
        "never_evaluated",
        "evaluated_before_edit",
        "evaluated_after_edit",
    ],
)
def test_the_changelist_flags_a_change_no_run_has_applied(
    staff_client, mock_site_context, is_enabled, last_evaluated_at, expected
):
    # Arrange
    with time_machine.travel(_FEB, tick=False):
        rule = RegistrationRuleFactory(
            is_enabled=is_enabled, last_evaluated_at=last_evaluated_at
        )

    # Act
    flagged = _flag_for(staff_client, rule)

    # Assert
    assert flagged is expected


@pytest.mark.django_db
def test_the_changelist_stops_flagging_a_rule_once_it_has_run(staff_client, rules_on):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on, is_enabled=True)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _flag_for(staff_client, rule) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("visibility", "expected"),
    [
        (CourseVisibility.PUBLISHED, False),
        (CourseVisibility.COMING_SOON, True),
        (CourseVisibility.HIDDEN, True),
    ],
)
def test_the_change_page_warns_when_the_course_is_not_published(
    staff_client, mock_site_context, visibility, expected
):
    # Arrange
    rule = RegistrationRuleFactory(course=CourseFactory(visibility=visibility))

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert any("not published" in w for w in _warnings(response)) is expected


@pytest.mark.django_db
def test_a_rule_on_an_unpublished_course_still_registers_learners(rules_on):
    # Arrange
    rule = RegistrationRuleFactory(
        organisation=rules_on,
        is_enabled=True,
        course=CourseFactory(visibility=CourseVisibility.HIDDEN),
    )
    learner = _learner_in(rules_on)
    drop_ambient_request()

    # Act
    evaluate_rule(rule.pk, rule.site_id)

    # Assert
    assert _active_learner_ids(rule.course) == {learner.pk}


@pytest.mark.django_db
def test_an_unapplied_change_with_the_switch_off_names_the_organisation(
    staff_client, mock_site_context
):
    # Arrange
    rule = RegistrationRuleFactory(is_enabled=True)

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert any(
        "switched off" in w and rule.organisation.name in w for w in _warnings(response)
    )


@pytest.mark.django_db
def test_an_unapplied_change_with_the_switch_on_names_the_task_worker(
    staff_client, rules_on
):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on, is_enabled=True)

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert any("task worker" in w for w in _warnings(response))


@pytest.mark.django_db
def test_an_unapplied_change_with_the_switch_on_does_not_blame_the_switch(
    staff_client, rules_on
):
    # Arrange
    rule = RegistrationRuleFactory(organisation=rules_on, is_enabled=True)

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert not any("switched off" in w for w in _warnings(response))


@pytest.mark.django_db
def test_an_applied_change_shows_no_warning(staff_client, rules_on):
    # Arrange
    rule = RegistrationRuleFactory(
        organisation=rules_on,
        is_enabled=True,
        last_evaluated_at=timezone.now() + timedelta(hours=1),
    )

    # Act
    response = _change_page(staff_client, rule)

    # Assert
    assert _warnings(response) == []
