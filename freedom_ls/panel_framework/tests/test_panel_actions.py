from __future__ import annotations

import json

import pytest
from guardian.shortcuts import assign_perm

from django import forms
from django.db.models import Model
from django.test import RequestFactory

from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    DeleteAction,
    EditAction,
    PanelAction,
)
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import _handle_action, _ResolvedAction

from .conftest import StubModel, _make_stub, _make_stub_child, make_staff_user

# -- Shared test form ---------------------------------------------------


class _StubModelForm(forms.ModelForm):
    class Meta:
        model = StubModel
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
    form_class = _StubModelForm
    form_title = "Create Item"
    label = "Create Item"
    action_name = "create_item"

    def get_success_url(self, instance: Model) -> str:
        return f"/items/{instance.pk}"

    def get_created_event_name(self) -> str:
        return "itemCreated"


# -- PanelAction base class tests ----------------------------------------


@pytest.mark.django_db
def test_panel_get_actions_returns_empty_list_by_default(mock_site_context):
    """Panel.get_actions() returns empty list by default."""
    item = _make_stub(name="test-item")
    panel = StubPanel(item)
    request = RequestFactory().get("/")
    assert panel.get_actions(request) == []


@pytest.mark.django_db
def test_panel_action_render_returns_button_html(mock_site_context):
    """PanelAction.render() returns button HTML."""
    item = _make_stub(name="action-render")
    panel = StubPanel(item)
    action = StubAction()
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = action.render(request, panel, "/test/base")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_renders_actions_when_present(mock_site_context):
    """Panel container renders action buttons when actions exist."""
    item = _make_stub(name="actions-present")

    class PanelWithAction(StubPanel):
        def get_actions(self, request, base_url=""):
            return [StubAction()]

    panel = PanelWithAction(item)
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = panel.render(request, base_url="/test")
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_no_actions_area_when_no_actions(mock_site_context):
    """Panel container renders no actions area when no actions."""
    item = _make_stub(name="no-actions")
    panel = StubPanel(item)
    request = RequestFactory().get("/")
    request.user = make_staff_user()
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
    request = RequestFactory().post("/", {"name": "New Item"})
    request.user = make_staff_user()
    assign_perm("freedom_ls_panel_framework.add_stubmodel", request.user)

    response = action.handle_submit(request, instance=None, base_url="/items")
    assert response.status_code == 204
    item = StubModel.objects.get(name="New Item")
    assert f"/items/{item.pk}" in response["HX-Redirect"]


@pytest.mark.django_db
def test_create_action_save_and_add_another_returns_empty_form_and_trigger(
    mock_site_context,
):
    """'Save and add another' returns re-rendered empty form + HX-Trigger event."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Item A", "action": "save_and_add"})
    request.user = make_staff_user()

    response = action.handle_submit(request, instance=None, base_url="/items")
    assert response.status_code == 200
    assert StubModel.objects.filter(name="Item A").exists()
    assert response["HX-Trigger"] == "itemCreated"
    content = response.content.decode()
    assert "Create Item" in content


@pytest.mark.django_db
def test_create_action_duplicate_name_returns_422(mock_site_context):
    """Duplicate name within site returns 422 with validation error."""
    _make_stub(name="Existing")
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Existing"})
    request.user = make_staff_user()

    response = action.handle_submit(request, instance=None, base_url="/items")
    assert response.status_code == 422


@pytest.mark.django_db
def test_create_action_has_permission_checks_add_perm(mock_site_context):
    """has_permission returns True only when user has add permission."""
    action = StubCreateAction()

    user_with_perm = make_staff_user()
    assign_perm("freedom_ls_panel_framework.add_stubmodel", user_with_perm)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request) is True

    user_without_perm = make_staff_user()
    request.user = user_without_perm
    assert action.has_permission(request) is False


@pytest.mark.django_db
def test_create_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks add permission."""
    action = StubCreateAction()
    user = make_staff_user()
    # No add permission
    request = RequestFactory().post("/", {"name": "Forbidden"})
    request.user = user

    resolved = _ResolvedAction(action, instance=None)
    response = _handle_action(request, resolved, base_url="/items")
    assert response.status_code == 403
    assert not StubModel.objects.filter(name="Forbidden").exists()


# -- EditAction tests ----------------------------------------------------


@pytest.mark.django_db
def test_edit_action_form_valid_saves_and_returns_trigger(mock_site_context):
    """Successful edit returns 204 + HX-Trigger with panelChanged."""
    item = _make_stub(name="Old Name")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )
    request = RequestFactory().post("/", {"name": "New Name"})
    request.user = make_staff_user()

    response = action.handle_submit(request, instance=item, base_url="/test")
    assert response.status_code == 204
    item.refresh_from_db()
    assert item.name == "New Name"
    trigger = json.loads(response["HX-Trigger"])
    assert "panelChanged" in trigger
    assert trigger["panelChanged"]["instanceTitle"] == "New Name"


@pytest.mark.django_db
def test_edit_action_duplicate_name_returns_422(mock_site_context):
    """Duplicate name returns 422 with validation error."""
    _make_stub(name="Existing-edit")
    item = _make_stub(name="Original")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )
    request = RequestFactory().post("/", {"name": "Existing-edit"})
    request.user = make_staff_user()

    response = action.handle_submit(request, instance=item, base_url="/test")
    assert response.status_code == 422


@pytest.mark.django_db
def test_edit_action_has_permission_checks_object_level_change_perm(mock_site_context):
    """has_permission checks object-level change permission."""
    item = _make_stub(name="edit-perm-check")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )

    user_with_perm = make_staff_user()
    assign_perm("freedom_ls_panel_framework.change_stubmodel", user_with_perm, item)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request) is True

    user_without_perm = make_staff_user()
    request.user = user_without_perm
    assert action.has_permission(request) is False


@pytest.mark.django_db
def test_edit_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks change permission."""
    item = _make_stub(name="Test-edit-403")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )
    user = make_staff_user()
    request = RequestFactory().post("/", {"name": "Changed"})
    request.user = user

    resolved = _ResolvedAction(action, instance=item)
    response = _handle_action(request, resolved, base_url="/test")
    assert response.status_code == 403
    item.refresh_from_db()
    assert item.name == "Test-edit-403"


# -- DeleteAction tests --------------------------------------------------


@pytest.mark.django_db
def test_delete_action_handle_submit_deletes_and_redirects(mock_site_context):
    """Successful deletion deletes instance and returns 204 + HX-Redirect."""
    item = _make_stub(name="to-delete")
    item_pk = item.pk
    action = DeleteAction(success_url="/items")

    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = action.handle_submit(request, instance=item, base_url="/test")
    assert response.status_code == 204
    assert response["HX-Redirect"] == "/items"
    assert not StubModel.objects.filter(pk=item_pk).exists()


@pytest.mark.django_db
def test_delete_action_cascade_summary_includes_related_objects(mock_site_context):
    """get_cascade_summary returns summary of related objects that will be deleted."""
    item = _make_stub(name="cascade-parent")
    _make_stub_child(parent=item)
    _make_stub_child(parent=item)

    action = DeleteAction(success_url="/items")
    summary = action.get_cascade_summary(item)
    assert len(summary) > 0
    summary_text = " ".join(summary).lower()
    assert "stub child" in summary_text


@pytest.mark.django_db
def test_delete_action_render_returns_confirmation_html(mock_site_context):
    """Rendered delete confirmation includes delete button and action URL."""
    item = _make_stub(name="delete-render")
    action = DeleteAction(success_url="/items")

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = action.render(request, item, "/test")
    assert "Delete" in html
    assert "/test/__actions/delete" in html


@pytest.mark.django_db
def test_delete_action_has_permission_checks_object_level_delete_perm(
    mock_site_context,
):
    """has_permission checks object-level delete permission."""
    item = _make_stub(name="delete-perm-check")
    action = DeleteAction(success_url="/items")

    user_with_perm = make_staff_user()
    assign_perm("freedom_ls_panel_framework.delete_stubmodel", user_with_perm, item)
    request = RequestFactory().get("/")
    request.user = user_with_perm
    assert action.has_permission(request, item) is True

    user_without_perm = make_staff_user()
    request.user = user_without_perm
    assert action.has_permission(request, item) is False


@pytest.mark.django_db
def test_delete_action_permission_denied_returns_403(mock_site_context):
    """_handle_action returns 403 when user lacks delete permission."""
    item = _make_stub(name="delete-403")
    action = DeleteAction(success_url="/items")

    user = make_staff_user()
    request = RequestFactory().delete("/")
    request.user = user

    resolved = _ResolvedAction(action, instance=item)
    response = _handle_action(request, resolved, base_url="/test")
    assert response.status_code == 403
    assert StubModel.objects.filter(pk=item.pk).exists()
