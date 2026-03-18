from __future__ import annotations

import json

import pytest
from guardian.shortcuts import assign_perm

# -- Shared test form ---------------------------------------------------
from django import forms
from django.db.models import Model
from django.test import RequestFactory

from freedom_ls.accounts.factories import UserFactory
from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    DeleteAction,
    EditAction,
    PanelAction,
)
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import _handle_action, _ResolvedAction
from freedom_ls.student_management.factories import (
    CohortCourseRegistrationFactory,
    CohortFactory,
    CohortMembershipFactory,
)
from freedom_ls.student_management.models import Cohort


class _CohortForm(forms.ModelForm):
    class Meta:
        model = Cohort
        fields = ["name"]


# -- Stubs ---------------------------------------------------------------


class StubPanel(Panel):
    title = "Test Panel"

    def get_content(self, request, base_url="", panel_name=""):
        return "<p>content</p>"


class StubAction(PanelAction):
    label = "Do Thing"
    variant = "primary"
    action_name = "do_thing"


class StubCreateAction(CreateInstanceAction):
    form_class = _CohortForm
    form_title = "Create Cohort"
    label = "Create Cohort"
    action_name = "create_cohort"

    def get_success_url(self, instance: Model) -> str:
        return f"/cohorts/{instance.pk}"

    def get_created_event_name(self) -> str:
        return "cohortCreated"


# -- PanelAction base class tests ----------------------------------------


@pytest.mark.django_db
def test_panel_get_actions_returns_empty_list_by_default(mock_site_context):
    """Panel.get_actions() returns empty list by default."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    request = RequestFactory().get("/")
    assert panel.get_actions(request) == []


@pytest.mark.django_db
def test_panel_action_render_returns_button_html(mock_site_context):
    """PanelAction.render() returns button HTML."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    action = StubAction()
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = action.render(request, panel, "/test/base")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_renders_actions_when_present(mock_site_context):
    """Panel container renders action buttons when actions exist."""
    cohort = CohortFactory()

    class PanelWithAction(StubPanel):
        def get_actions(self, request, base_url=""):
            return [StubAction()]

    panel = PanelWithAction(cohort)
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = panel.render(request, base_url="/test")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_no_actions_area_when_no_actions(mock_site_context):
    """Panel container renders no actions area when no actions."""
    cohort = CohortFactory()
    panel = StubPanel(cohort)
    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = panel.render(request, base_url="/test")
    assert "Do Thing" not in html


@pytest.mark.django_db
def test_panel_action_has_permission_returns_true_by_default(mock_site_context):
    """PanelAction.has_permission() returns True by default."""
    action = StubAction()
    request = RequestFactory().get("/")
    assert action.has_permission(request) is True


# -- CreateInstanceAction tests ------------------------------------------


@pytest.mark.django_db
def test_create_action_form_valid_creates_instance_and_redirects(mock_site_context):
    """Successful form submission creates instance and returns 204 + HX-Redirect."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "New Cohort"})
    request.user = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", request.user)

    response = action.handle_submit(request, instance=None, base_url="/cohorts")
    assert response.status_code == 204
    cohort = Cohort.objects.get(name="New Cohort")
    assert f"/cohorts/{cohort.pk}" in response["HX-Redirect"]


@pytest.mark.django_db
def test_create_action_save_and_add_another_returns_empty_form_and_trigger(
    mock_site_context,
):
    """'Save and add another' returns re-rendered empty form + HX-Trigger event."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Cohort A", "action": "save_and_add"})
    request.user = UserFactory(staff=True)

    response = action.handle_submit(request, instance=None, base_url="/cohorts")
    assert response.status_code == 200
    assert Cohort.objects.filter(name="Cohort A").exists()
    assert response["HX-Trigger"] == "cohortCreated"
    content = response.content.decode()
    assert "Create Cohort" in content


@pytest.mark.django_db
def test_create_action_duplicate_name_returns_422(mock_site_context):
    """Duplicate name within site returns 422 with validation error."""
    CohortFactory(name="Existing")
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Existing"})
    request.user = UserFactory(staff=True)

    response = action.handle_submit(request, instance=None, base_url="/cohorts")
    assert response.status_code == 422


@pytest.mark.django_db
def test_create_action_has_permission_checks_add_perm(mock_site_context):
    """has_permission returns True only when user has add permission."""
    action = StubCreateAction()

    user_with_perm = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.add_cohort", user_with_perm)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request) is True

    user_without_perm = UserFactory(staff=True)
    request.user = user_without_perm
    assert action.has_permission(request) is False


@pytest.mark.django_db
def test_create_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks add permission."""
    action = StubCreateAction()
    user = UserFactory(staff=True)
    # No add_cohort permission
    request = RequestFactory().post("/", {"name": "Forbidden"})
    request.user = user

    resolved = _ResolvedAction(action, instance=None)
    response = _handle_action(request, resolved, base_url="/cohorts")
    assert response.status_code == 403
    assert not Cohort.objects.filter(name="Forbidden").exists()


# -- EditAction tests ----------------------------------------------------


@pytest.mark.django_db
def test_edit_action_form_valid_saves_and_returns_trigger(mock_site_context):
    """Successful edit returns 204 + HX-Trigger with panelChanged."""
    cohort = CohortFactory(name="Old Name")
    action = EditAction(
        form_class=_CohortForm,
        form_title="Edit Cohort",
        instance=cohort,
    )
    request = RequestFactory().post("/", {"name": "New Name"})
    request.user = UserFactory(staff=True)

    response = action.handle_submit(request, instance=cohort, base_url="/test")
    assert response.status_code == 204
    cohort.refresh_from_db()
    assert cohort.name == "New Name"
    trigger = json.loads(response["HX-Trigger"])
    assert "panelChanged" in trigger
    assert trigger["panelChanged"]["instanceTitle"] == "New Name"


@pytest.mark.django_db
def test_edit_action_duplicate_name_returns_422(mock_site_context):
    """Duplicate name returns 422 with validation error."""
    CohortFactory(name="Existing")
    cohort = CohortFactory(name="Original")
    action = EditAction(
        form_class=_CohortForm,
        form_title="Edit Cohort",
        instance=cohort,
    )
    request = RequestFactory().post("/", {"name": "Existing"})
    request.user = UserFactory(staff=True)

    response = action.handle_submit(request, instance=cohort, base_url="/test")
    assert response.status_code == 422


@pytest.mark.django_db
def test_edit_action_has_permission_checks_object_level_change_perm(mock_site_context):
    """has_permission checks object-level change permission."""
    cohort = CohortFactory()
    action = EditAction(
        form_class=_CohortForm,
        form_title="Edit Cohort",
        instance=cohort,
    )

    user_with_perm = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.change_cohort", user_with_perm, cohort)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request) is True

    user_without_perm = UserFactory(staff=True)
    request.user = user_without_perm
    assert action.has_permission(request) is False


@pytest.mark.django_db
def test_edit_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks change permission."""
    cohort = CohortFactory(name="Test")
    action = EditAction(
        form_class=_CohortForm,
        form_title="Edit Cohort",
        instance=cohort,
    )
    user = UserFactory(staff=True)
    request = RequestFactory().post("/", {"name": "Changed"})
    request.user = user

    resolved = _ResolvedAction(action, instance=cohort)
    response = _handle_action(request, resolved, base_url="/test")
    assert response.status_code == 403
    cohort.refresh_from_db()
    assert cohort.name == "Test"


# -- DeleteAction tests --------------------------------------------------


@pytest.mark.django_db
def test_delete_action_handle_submit_deletes_and_redirects(mock_site_context):
    """Successful deletion deletes instance and returns 204 + HX-Redirect."""
    cohort = CohortFactory()
    cohort_pk = cohort.pk
    action = DeleteAction(success_url="/cohorts")

    request = RequestFactory().delete("/")
    request.user = UserFactory(staff=True)

    response = action.handle_submit(request, instance=cohort, base_url="/test")
    assert response.status_code == 204
    assert response["HX-Redirect"] == "/cohorts"
    assert not Cohort.objects.filter(pk=cohort_pk).exists()


@pytest.mark.django_db
def test_delete_action_cascade_summary_includes_related_objects(mock_site_context):
    """get_cascade_summary returns summary of related objects that will be deleted."""
    cohort = CohortFactory()
    CohortMembershipFactory(cohort=cohort)
    CohortCourseRegistrationFactory(cohort=cohort)

    action = DeleteAction(success_url="/cohorts")
    summary = action.get_cascade_summary(cohort)
    assert len(summary) > 0
    # Should mention related objects
    summary_text = " ".join(summary).lower()
    assert (
        "cohort membership" in summary_text
        or "cohort course registration" in summary_text
    )


@pytest.mark.django_db
def test_delete_action_render_returns_confirmation_html(mock_site_context):
    """Rendered delete confirmation includes delete button and action URL."""
    cohort = CohortFactory()
    action = DeleteAction(success_url="/cohorts")

    request = RequestFactory().get("/")
    request.user = UserFactory(staff=True)
    html = action.render(request, cohort, "/test")
    assert "Delete" in html
    assert "/test/__actions/delete" in html


@pytest.mark.django_db
def test_delete_action_has_permission_checks_object_level_delete_perm(
    mock_site_context,
):
    """has_permission checks object-level delete permission."""
    cohort = CohortFactory()
    action = DeleteAction(success_url="/cohorts")

    user_with_perm = UserFactory(staff=True)
    assign_perm("freedom_ls_student_management.delete_cohort", user_with_perm, cohort)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request, cohort) is True

    user_without_perm = UserFactory(staff=True)
    request.user = user_without_perm
    assert action.has_permission(request, cohort) is False


@pytest.mark.django_db
def test_delete_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks delete permission."""
    cohort = CohortFactory()
    action = DeleteAction(success_url="/cohorts")

    user = UserFactory(staff=True)
    request = RequestFactory().delete("/")
    request.user = user

    resolved = _ResolvedAction(action, instance=cohort)
    response = _handle_action(request, resolved, base_url="/test")
    assert response.status_code == 403
    assert Cohort.objects.filter(pk=cohort.pk).exists()
