"""Tests for the hr_attributes list admins."""

from __future__ import annotations

import pytest

from django.urls import reverse

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.hr_attributes"):
    pytest.skip("hr_attributes not installed", allow_module_level=True)

from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
)
from freedom_ls.hr_attributes.models import (
    LearnerHRAttributes,
    OrganisationHRSettings,
)

CASES = [
    pytest.param(JobTitleFactory, "jobtitle", "job_title", id="job_title"),
    pytest.param(DepartmentFactory, "department", "department", id="department"),
    pytest.param(LocationFactory, "location", "location", id="location"),
]


def _url(model_name: str, view: str, *args: object) -> str:
    return reverse(f"admin:freedom_ls_hr_attributes_{model_name}_{view}", args=args)


def _changelist_names(response) -> set[str]:
    return {entry.name for entry in response.context["cl"].result_list}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_changelist_loads(staff_client, factory_class, model_name, field):
    # Arrange
    entry = factory_class()

    # Act
    response = staff_client.get(_url(model_name, "changelist"))

    # Assert
    assert response.status_code == 200
    assert _changelist_names(response) == {entry.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_organisation_filter_narrows_to_that_organisation(
    staff_client, factory_class, model_name, field
):
    # Arrange
    wanted = factory_class()
    factory_class()

    # Act
    response = staff_client.get(
        _url(model_name, "changelist"),
        {"organisation__id__exact": wanted.organisation.pk},
    )

    # Assert
    assert _changelist_names(response) == {wanted.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_inactive_filter_narrows_to_inactive_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    inactive = factory_class(is_active=False)
    factory_class(is_active=True)

    # Act
    response = staff_client.get(
        _url(model_name, "changelist"), {"is_active__exact": "0"}
    )

    # Assert
    assert _changelist_names(response) == {inactive.name}


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_deactivate_action_deactivates_the_selected_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    first, second = factory_class(), factory_class()

    # Act
    response = staff_client.post(
        _url(model_name, "changelist"),
        {"action": "deactivate_selected", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    # Assert
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.is_active, second.is_active) == (False, False)
    assert "2 entries deactivated." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_activate_action_activates_the_selected_entries(
    staff_client, factory_class, model_name, field
):
    # Arrange
    first = factory_class(is_active=False)
    second = factory_class(is_active=False)

    # Act
    response = staff_client.post(
        _url(model_name, "changelist"),
        {"action": "activate_selected", "_selected_action": [first.pk, second.pk]},
        follow=True,
    )

    # Assert
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.is_active, second.is_active) == (True, True)
    assert "2 entries activated." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_delete_of_a_held_entry_is_refused_and_names_the_attributes_row(
    staff_client, factory_class, model_name, field
):
    # Arrange
    entry = factory_class()
    LearnerHRAttributesFactory(**{field: entry})

    # Act
    response = staff_client.post(_url(model_name, "delete", entry.pk), {"post": "yes"})

    # Assert
    assert response.status_code == 200
    assert type(entry).objects.filter(pk=entry.pk).exists()
    assert "HR attributes for" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_delete_of_an_unused_entry_deletes_it(
    staff_client, factory_class, model_name, field
):
    # Arrange
    entry = factory_class()

    # Act
    staff_client.post(_url(model_name, "delete", entry.pk), {"post": "yes"})

    # Assert
    assert not type(entry).objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_add_form_with_a_case_variant_duplicate_creates_no_row(
    staff_client, factory_class, model_name, field
):
    # Arrange
    existing = factory_class(name="Finance")
    organisation = existing.organisation
    OrganisationFactory()

    # Act
    response = staff_client.post(
        _url(model_name, "add"),
        {"organisation": organisation.pk, "name": "FINANCE", "is_active": "on"},
    )

    # Assert
    assert response.status_code == 200
    assert type(existing).objects.count() == 1
    assert "An entry with this name already exists" in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_change_page_keeps_the_organisation_of_an_existing_entry(
    staff_client, factory_class, model_name, field
):
    # Arrange
    entry = factory_class(name="Finance")
    original_organisation = entry.organisation
    LearnerHRAttributesFactory(**{field: entry})
    other_organisation = OrganisationFactory()

    # Act
    response = staff_client.post(
        _url(model_name, "change", entry.pk),
        {"organisation": other_organisation.pk, "name": "Finance", "is_active": "on"},
    )

    # Assert
    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.organisation == original_organisation


@pytest.mark.django_db
@pytest.mark.parametrize(("factory_class", "model_name", "field"), CASES)
def test_change_page_refuses_renaming_to_a_case_variant_duplicate(
    staff_client, factory_class, model_name, field
):
    # Arrange
    existing = factory_class(name="Finance")
    entry = factory_class(organisation=existing.organisation, name="Operations")

    # Act
    response = staff_client.post(
        _url(model_name, "change", entry.pk),
        {"name": "FINANCE", "is_active": "on"},
    )

    # Assert
    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.name == "Operations"
    assert "An entry with this name already exists" in response.content.decode()


LEARNER_CHANGE_URL_NAME = "admin:freedom_ls_learner_management_learner_change"


def _change_payload(response, **overrides: str) -> dict[str, str]:
    """The admin change form's own values, ready to post straight back."""
    form = response.context["adminform"].form
    payload = {
        name: "" if form.initial.get(name) is None else str(form.initial.get(name, ""))
        for name in form.fields
    }
    for inline in response.context["inline_admin_formsets"]:
        prefix = inline.formset.prefix
        payload[f"{prefix}-TOTAL_FORMS"] = "0"
        payload[f"{prefix}-INITIAL_FORMS"] = "0"
        payload[f"{prefix}-MIN_NUM_FORMS"] = "0"
        payload[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    payload.update(overrides)
    return payload


def _inline_models(response) -> set[type]:
    return {
        inline.formset.model for inline in response.context["inline_admin_formsets"]
    }


@pytest.mark.django_db
def test_learner_change_page_carries_no_hr_attributes_inline(staff_client):
    # Arrange
    learner = LearnerFactory()

    # Act
    response = staff_client.get(reverse(LEARNER_CHANGE_URL_NAME, args=[learner.pk]))

    # Assert
    assert response.status_code == 200
    assert learner.user.email in response.content.decode()
    assert LearnerHRAttributes not in _inline_models(response)


ORGANISATION_CHANGE_URL_NAME = "admin:freedom_ls_organisations_organisation_change"
ORGANISATION_ADD_URL_NAME = "admin:freedom_ls_organisations_organisation_add"


@pytest.mark.django_db
def test_organisation_change_page_carries_the_hr_settings_inline(staff_client):
    # Arrange
    organisation = OrganisationFactory()

    # Act
    response = staff_client.get(
        reverse(ORGANISATION_CHANGE_URL_NAME, args=[organisation.pk])
    )

    # Assert
    assert OrganisationHRSettings in _inline_models(response)


@pytest.mark.django_db
def test_organisation_add_page_carries_no_inlines(staff_client):
    # Act
    response = staff_client.get(reverse(ORGANISATION_ADD_URL_NAME))

    # Assert
    assert list(response.context["inline_admin_formsets"]) == []


@pytest.mark.django_db
def test_ticking_registration_rules_creates_the_settings_row_switched_on(
    staff_client,
):
    # Arrange
    organisation = OrganisationFactory()
    url = reverse(ORGANISATION_CHANGE_URL_NAME, args=[organisation.pk])
    payload = _change_payload(
        staff_client.get(url),
        **{
            "hr_settings-TOTAL_FORMS": "1",
            "hr_settings-INITIAL_FORMS": "0",
            "hr_settings-0-organisation": str(organisation.pk),
            "hr_settings-0-registration_rules_enabled": "on",
        },
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    settings_row = OrganisationHRSettings.objects.get(organisation=organisation)
    assert response.status_code == 302
    assert settings_row.registration_rules_enabled is True


@pytest.mark.django_db
def test_saving_organisation_with_the_switch_untouched_creates_no_row(staff_client):
    # Arrange
    organisation = OrganisationFactory()
    url = reverse(ORGANISATION_CHANGE_URL_NAME, args=[organisation.pk])
    payload = _change_payload(
        staff_client.get(url),
        **{
            "hr_settings-TOTAL_FORMS": "1",
            "hr_settings-INITIAL_FORMS": "0",
            "hr_settings-0-organisation": str(organisation.pk),
        },
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    assert response.status_code == 302
    assert not OrganisationHRSettings.objects.filter(organisation=organisation).exists()
