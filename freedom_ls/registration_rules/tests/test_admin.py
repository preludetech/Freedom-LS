"""Tests for the registration rule admin."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.content_engine.factories import CourseFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.registration_rules"):
    pytest.skip("registration_rules not installed", allow_module_level=True)

from freedom_ls.registration_rules.factories import RegistrationRuleFactory
from freedom_ls.registration_rules.models import RegistrationRule


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
