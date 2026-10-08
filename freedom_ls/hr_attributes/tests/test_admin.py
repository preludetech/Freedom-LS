"""Tests for the hr_attributes list admins."""

from __future__ import annotations

import pytest

from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from django.urls.resolvers import ResolverMatch

from freedom_ls.learner_management.factories import LearnerFactory
from freedom_ls.organisations.factories import OrganisationFactory
from freedom_ls.tests.app_guards import app_not_installed

if app_not_installed("freedom_ls.hr_attributes"):
    pytest.skip("hr_attributes not installed", allow_module_level=True)

from freedom_ls.hr_attributes.admin import LearnerHRAttributesInline, _picker_scope
from freedom_ls.hr_attributes.factories import (
    DepartmentFactory,
    JobTitleFactory,
    LearnerHRAttributesFactory,
    LocationFactory,
)
from freedom_ls.hr_attributes.models import LearnerHRAttributes

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


LEARNER_CHANGE_URL_NAME = "admin:freedom_ls_learner_management_learner_change"
LEARNER_ADD_URL_NAME = "admin:freedom_ls_learner_management_learner_add"


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


def _attributes_formset(response):
    return next(
        inline
        for inline in response.context["inline_admin_formsets"]
        if inline.formset.model is LearnerHRAttributes
    )


def _job_title_choice_labels(response) -> list[str]:
    formset = _attributes_formset(response)
    field = formset.formset.forms[0].fields["job_title"]
    return [label for value, label in field.choices if value]


@pytest.mark.django_db
def test_learner_change_page_carries_the_hr_attributes_inline(staff_client):
    # Arrange
    learner = LearnerFactory()

    # Act
    response = staff_client.get(reverse(LEARNER_CHANGE_URL_NAME, args=[learner.pk]))

    # Assert
    assert LearnerHRAttributes in _inline_models(response)


@pytest.mark.django_db
def test_learner_add_page_carries_no_inlines(staff_client):
    # Act
    response = staff_client.get(reverse(LEARNER_ADD_URL_NAME))

    # Assert
    assert list(response.context["inline_admin_formsets"]) == []


@pytest.mark.django_db
def test_job_title_picker_offers_active_titles_and_the_held_inactive_one(
    staff_client,
):
    # Arrange
    attributes = LearnerHRAttributesFactory()
    organisation = attributes.learner.organisation
    attributes.job_title.is_active = False
    attributes.job_title.name = "Held"
    attributes.job_title.save()
    JobTitleFactory(organisation=organisation, name="Offered")
    JobTitleFactory(organisation=organisation, name="Withdrawn", is_active=False)
    JobTitleFactory(name="Elsewhere")

    # Act
    response = staff_client.get(
        reverse(LEARNER_CHANGE_URL_NAME, args=[attributes.learner.pk])
    )

    # Assert
    assert _job_title_choice_labels(response) == ["Held (inactive)", "Offered"]


@pytest.mark.django_db
def test_saving_filled_inline_creates_the_attributes_row(staff_client):
    # Arrange
    learner = LearnerFactory()
    job_title = JobTitleFactory(organisation=learner.organisation)
    url = reverse(LEARNER_CHANGE_URL_NAME, args=[learner.pk])
    payload = _change_payload(
        staff_client.get(url),
        **{
            "hr_attributes-TOTAL_FORMS": "1",
            "hr_attributes-INITIAL_FORMS": "0",
            "hr_attributes-0-learner": str(learner.pk),
            "hr_attributes-0-job_title": str(job_title.pk),
            "hr_attributes-0-organisation_start_date": "2024-01-15",
        },
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    attributes = LearnerHRAttributes.objects.get(learner=learner)
    assert response.status_code == 302
    assert attributes.job_title == job_title
    assert attributes.organisation_start_date.isoformat() == "2024-01-15"


@pytest.mark.django_db
def test_saving_untouched_inline_creates_no_row(staff_client):
    # Arrange
    learner = LearnerFactory()
    url = reverse(LEARNER_CHANGE_URL_NAME, args=[learner.pk])
    payload = _change_payload(
        staff_client.get(url),
        **{
            "hr_attributes-TOTAL_FORMS": "1",
            "hr_attributes-INITIAL_FORMS": "0",
            "hr_attributes-0-learner": str(learner.pk),
        },
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    assert response.status_code == 302
    assert not LearnerHRAttributes.objects.filter(learner=learner).exists()


def _move_payload(staff_client, attributes, other_organisation, **entry_keys: str):
    learner = attributes.learner
    url = reverse(LEARNER_CHANGE_URL_NAME, args=[learner.pk])
    return url, _change_payload(
        staff_client.get(url),
        organisation=str(other_organisation.pk),
        **{
            "hr_attributes-TOTAL_FORMS": "1",
            "hr_attributes-INITIAL_FORMS": "1",
            "hr_attributes-0-id": str(attributes.pk),
            "hr_attributes-0-learner": str(learner.pk),
            "hr_attributes-0-job_title": entry_keys["job_title"],
            "hr_attributes-0-department": entry_keys["department"],
            "hr_attributes-0-location": entry_keys["location"],
        },
    )


@pytest.mark.django_db
def test_moving_a_learner_who_holds_entries_is_refused_on_the_entry_field(
    staff_client,
):
    # Arrange
    attributes = LearnerHRAttributesFactory()
    learner = attributes.learner
    original_organisation = learner.organisation
    url, payload = _move_payload(
        staff_client,
        attributes,
        OrganisationFactory(),
        job_title=str(attributes.job_title.pk),
        department=str(attributes.department.pk),
        location=str(attributes.location.pk),
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    learner.refresh_from_db()
    form = _attributes_formset(response).formset.forms[0]
    assert response.status_code == 200
    assert learner.organisation == original_organisation
    assert "job_title" in form.errors
    assert form.errors["job_title"] == [
        "Choose a job title from this learner's organisation."
    ]


@pytest.mark.django_db
def test_moving_a_learner_with_the_entries_cleared_succeeds(staff_client):
    # Arrange
    attributes = LearnerHRAttributesFactory()
    learner = attributes.learner
    other_organisation = OrganisationFactory()
    url, payload = _move_payload(
        staff_client,
        attributes,
        other_organisation,
        job_title="",
        department="",
        location="",
    )

    # Act
    response = staff_client.post(url, payload)

    # Assert
    learner.refresh_from_db()
    attributes.refresh_from_db()
    assert response.status_code == 302
    assert learner.organisation == other_organisation
    assert attributes.job_title is None
    assert attributes.department is None
    assert attributes.location is None


@pytest.mark.parametrize("learner_id", ["not-a-uuid", None, ""])
def test_picker_scope_is_none_without_a_valid_learner_id(learner_id):
    # Act / Assert
    assert _picker_scope(learner_id, "job_title") is None


@pytest.mark.django_db
@pytest.mark.parametrize("object_id", ["not-a-uuid", None])
def test_the_picker_offers_nothing_without_a_valid_learner_id(
    mock_site_context, object_id
):
    # Arrange
    JobTitleFactory()
    request = RequestFactory().get("/")
    request.resolver_match = ResolverMatch(
        func=lambda *args, **kwargs: None,
        args=(),
        kwargs={} if object_id is None else {"object_id": object_id},
    )
    inline = LearnerHRAttributesInline(LearnerHRAttributes, admin.site)
    db_field = LearnerHRAttributes._meta.get_field("job_title")

    # Act
    formfield = inline.formfield_for_foreignkey(db_field, request)

    # Assert
    assert formfield is not None
    assert list(formfield.queryset) == []
