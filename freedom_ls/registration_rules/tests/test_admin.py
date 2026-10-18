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

from freedom_ls.registration_rules.factories import (
    RegistrationRuleFactory,
    RuleRegistrationFactory,
)
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration


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
