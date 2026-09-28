from __future__ import annotations

import json

import pytest
from guardian.shortcuts import assign_perm
from pytest_mock import MockerFixture

from django import forms
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    DeleteAction,
    EditAction,
    PanelAction,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import (
    SectionConfigBase,
    _handle_action,
    _ResolvedAction,
)

from .conftest import (
    StubGrandchild,
    StubModel,
    _make_stub,
    _make_stub_child,
    _make_stub_protected_child,
    make_staff_user,
)
from .stub_panels import RecordingCapabilityConfig
from .stub_panels import StubReadOnlyAction

# -- Shared test form ---------------------------------------------------


class _StubModelForm(forms.ModelForm):
    class Meta:
        model = StubModel
        fields = ["name"]


# -- Stubs ---------------------------------------------------------------


class StubPanel(Panel):
    title = "Test Panel"


class StubAction(PanelAction):
    label = "Do Thing"
    variant = "primary"
    action_name = "do_thing"


class StubCreateAction(CreateInstanceAction):
    form_class = _StubModelForm
    form_title = "Create Item"
    label = "Create Item"
    action_name = "create_item"
    success_events = ("itemChanged",)

    def get_success_url(self, instance: Model) -> str:
        return f"/items/{instance.pk}"


def _ctx(
    request: HttpRequest, instance: Model | None = None, base_url: str = "/test"
) -> PanelContext:
    return PanelContext(
        request=request,
        instance=instance,
        base_url=base_url,
        name="",
        config=RecordingCapabilityConfig,
    )


def _render(action: PanelAction, ctx: PanelContext) -> str:
    return render_to_string(
        action.template_name, action.get_context_data(ctx), request=ctx.request
    )


def _render_panel(panel: Panel) -> str:
    return render_to_string(
        panel.template_name, panel.get_context_data(), request=panel.request
    )


# -- PanelAction base class tests ----------------------------------------


@pytest.mark.django_db
def test_panel_get_actions_returns_empty_list_by_default(
    mock_site_context: Site,
) -> None:
    """Panel.get_actions() returns empty list by default."""
    item = _make_stub(name="test-item")
    panel = StubPanel(_ctx(RequestFactory().get("/"), item))
    assert panel.get_actions() == []


@pytest.mark.django_db
def test_panel_action_render_returns_button_html(mock_site_context: Site) -> None:
    """PanelAction renders its button through its own template."""
    item = _make_stub(name="action-render")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = _render(StubAction(), _ctx(request, item, "/test/base"))
    assert "Do Thing" in html


def test_panel_action_url_hangs_off_its_owners_base_url() -> None:
    context = StubAction().get_context_data(
        _ctx(RequestFactory().get("/"), None, "/a/b")
    )
    assert context["action_url"] == "/a/b/__actions/do_thing"


@pytest.mark.django_db
def test_panel_container_renders_actions_when_present(mock_site_context: Site) -> None:
    """Panel container renders action buttons when actions exist."""
    item = _make_stub(name="actions-present")

    class PanelWithAction(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [StubAction()]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = _render_panel(PanelWithAction(_ctx(request, item)))
    assert "Do Thing" in html


@pytest.mark.django_db
def test_panel_container_no_actions_area_when_no_actions(
    mock_site_context: Site,
) -> None:
    """Panel container renders no actions area when no actions."""
    item = _make_stub(name="no-actions")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = _render_panel(StubPanel(_ctx(request, item)))
    assert "Do Thing" not in html


def test_panel_action_has_permission_returns_true_when_it_declares_no_capability() -> (
    None
):
    """The default has_permission needs no capability check at all when the
    action declares none."""
    action = StubAction()
    request = RequestFactory().get("/")
    assert action.has_permission(_ctx(request)) is True


@pytest.mark.django_db
def test_a_list_level_create_action_is_asked_about_ctx_scope(
    mock_site_context: Site,
) -> None:
    """A create action with no bound instance is a list-level action: the
    permission check runs against the list's own scope object."""
    scope = _make_stub(name="list-scope")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = PanelContext(
        request=request,
        instance=None,
        base_url="/items",
        name="",
        config=RecordingCapabilityConfig,
        scope=scope,
    )

    StubCreateAction().has_permission(ctx)

    assert RecordingCapabilityConfig.asked == [
        ("freedom_ls_panel_framework.add_stubmodel", scope)
    ]


@pytest.mark.django_db
def test_a_create_action_inside_an_instance_view_is_asked_about_ctx_instance(
    mock_site_context: Site,
) -> None:
    instance = _make_stub(name="instance-scope")
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    StubCreateAction().has_permission(_ctx(request, instance))

    assert RecordingCapabilityConfig.asked == [
        ("freedom_ls_panel_framework.add_stubmodel", instance)
    ]


@pytest.mark.django_db
def test_built_in_actions_deny_under_a_config_left_at_its_default(
    mock_site_context: Site,
) -> None:
    """CreateInstanceAction, EditAction and DeleteAction all deny when the
    bound config never overrides has_capability."""
    item = _make_stub(name="default-deny")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = PanelContext(
        request=request,
        instance=item,
        base_url="/items",
        name="",
        config=SectionConfigBase,
    )

    assert StubCreateAction().has_permission(ctx) is False
    assert (
        EditAction(
            form_class=_StubModelForm, form_title="Edit Item", instance=item
        ).has_permission(ctx)
        is False
    )
    assert DeleteAction(success_url="/items").has_permission(ctx) is False


@pytest.mark.django_db
def test_delete_action_denies_with_no_instance(mock_site_context: Site) -> None:
    """DeleteAction never falls back to a list-level scope -- there is
    nothing to delete without a bound instance."""
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    scope = _make_stub(name="delete-no-instance-scope")
    ctx = PanelContext(
        request=request,
        instance=None,
        base_url="/items",
        name="",
        config=RecordingCapabilityConfig,
        scope=scope,
    )

    assert DeleteAction(success_url="/items").has_permission(ctx) is False


# -- CreateInstanceAction tests ------------------------------------------


@pytest.mark.django_db
def test_create_action_form_valid_creates_instance_and_redirects(
    mock_site_context: Site,
) -> None:
    """ "Save" creates the instance and answers 204 with HX-Location, never
    HX-Redirect."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "New Item"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    assert response.status_code == 204
    item = StubModel.objects.get(name="New Item")
    assert response["HX-Trigger"] == build_hx_trigger(
        {"itemChanged": [str(item.pk)]}, close_modal=True
    )
    assert json.loads(response["HX-Location"]) == {
        "path": f"/items/{item.pk}",
        "target": "#main-content",
        "swap": "outerHTML",
    }
    assert "HX-Redirect" not in response


@pytest.mark.django_db
def test_create_action_save_and_add_another_returns_empty_form_and_trigger(
    mock_site_context: Site,
) -> None:
    """'Save and add another' returns 200 with the blank form and the domain
    event, and never closes the modal."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Item A", "action": "save_and_add"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    assert response.status_code == 200
    item = StubModel.objects.get(name="Item A")
    assert response["HX-Trigger"] == build_hx_trigger({"itemChanged": [str(item.pk)]})
    assert "HX-Location" not in response
    assert "HX-Redirect" not in response
    content = response.content.decode()
    assert "Create Item" in content


@pytest.mark.django_db
def test_create_action_duplicate_name_returns_422(mock_site_context: Site) -> None:
    """Duplicate name within site returns 422 with validation error."""
    _make_stub(name="Existing")
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Existing"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))
    assert response.status_code == 422
    content = response.content.decode()
    assert "data-error-summary" in content
    assert 'aria-invalid="true"' in content


@pytest.mark.django_db
def test_create_action_has_permission_reflects_the_configs_answer(
    mock_site_context: Site,
) -> None:
    action = StubCreateAction()
    item = _make_stub(name="create-permission-check")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = _ctx(request, item)

    RecordingCapabilityConfig.reset(answer=True)
    assert action.has_permission(ctx) is True

    RecordingCapabilityConfig.reset(answer=False)
    assert action.has_permission(ctx) is False


@pytest.mark.django_db
def test_create_action_permission_denied_raises_for_a_plain_request(
    mock_site_context: Site,
) -> None:
    """A plain (non-htmx) denial raises PermissionDenied, so the site's own
    403 page renders."""
    scope = _make_stub(name="create-403-scope")
    RecordingCapabilityConfig.reset(answer=False, scope=scope)
    action = StubCreateAction()
    user = make_staff_user()
    request = RequestFactory().post("/", {"name": "Forbidden"})
    request.user = user

    resolved = _ResolvedAction(action, _ctx(request, None, "/items"))
    with pytest.raises(PermissionDenied):
        _handle_action(request, resolved)
    assert not StubModel.objects.filter(name="Forbidden").exists()


@pytest.mark.django_db
def test_create_action_permission_denied_returns_403_fragment_for_htmx(
    mock_site_context: Site,
) -> None:
    """An htmx denial answers with the action_denied fragment, at 403, with
    the framework's default "who to ask" copy."""
    scope = _make_stub(name="create-403-htmx-scope")
    RecordingCapabilityConfig.reset(answer=False, scope=scope)
    action = StubCreateAction()
    user = make_staff_user()
    request = RequestFactory().post("/", {"name": "Forbidden"}, HTTP_HX_REQUEST="true")
    request.user = user

    resolved = _ResolvedAction(action, _ctx(request, None, "/items"))
    response = _handle_action(request, resolved)
    assert isinstance(response, HttpResponse)
    assert response.status_code == 403
    html = response.content.decode()
    assert "data-htmx-swap-error" in html
    assert "You can't use “Create Item” here any more" in html
    assert "Ask an administrator." in html
    assert "Close" in html
    assert not StubModel.objects.filter(name="Forbidden").exists()


# -- EditAction tests ----------------------------------------------------


@pytest.mark.django_db
def test_edit_action_form_valid_saves_and_returns_trigger(
    mock_site_context: Site,
) -> None:
    """A successful edit answers 204 with closeModal, its declared domain
    events and the new instance title, never HX-Redirect."""
    item = _make_stub(name="Old Name")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
        success_events=("itemChanged",),
    )
    request = RequestFactory().post("/", {"name": "New Name"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 204
    item.refresh_from_db()
    assert item.name == "New Name"
    assert response["HX-Trigger"] == build_hx_trigger(
        {"itemChanged": [str(item.pk)]}, close_modal=True, title="New Name"
    )
    assert "HX-Redirect" not in response


@pytest.mark.django_db
def test_edit_action_duplicate_name_returns_422(mock_site_context: Site) -> None:
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

    response = action.handle_submit(_ctx(request, item))
    assert response.status_code == 422
    content = response.content.decode()
    assert "data-error-summary" in content
    assert 'aria-invalid="true"' in content


@pytest.mark.django_db
def test_edit_action_has_permission_reflects_the_configs_answer(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="edit-permission-check")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = _ctx(request, item)

    RecordingCapabilityConfig.reset(answer=True)
    assert action.has_permission(ctx) is True

    RecordingCapabilityConfig.reset(answer=False)
    assert action.has_permission(ctx) is False


@pytest.mark.django_db
def test_edit_action_permission_denied_raises_for_a_plain_request(
    mock_site_context: Site,
) -> None:
    """A plain (non-htmx) denial raises PermissionDenied, so the site's own
    403 page renders."""
    RecordingCapabilityConfig.reset(answer=False)
    item = _make_stub(name="Test-edit-403")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
    )
    user = make_staff_user()
    request = RequestFactory().post("/", {"name": "Changed"})
    request.user = user

    resolved = _ResolvedAction(action, _ctx(request, item))
    with pytest.raises(PermissionDenied):
        _handle_action(request, resolved)
    item.refresh_from_db()
    assert item.name == "Test-edit-403"


@pytest.mark.django_db
def test_rendering_a_panel_with_a_form_action_never_builds_its_form(
    mock_site_context: Site, mocker: MockerFixture
) -> None:
    """Rendering a panel renders the action's trigger, never its fragment:
    building the form is deferred to a GET of the action's own URL."""
    item = _make_stub(name="lazy-edit")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )
    get_form = mocker.patch.object(EditAction, "get_form")

    class PanelWithEdit(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [action]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    assign_perm("freedom_ls_panel_framework.change_stubmodel", request.user, item)
    ctx = _ctx(request, item)
    html = _render_panel(PanelWithEdit(ctx))

    get_form.assert_not_called()
    assert f'hx-get="{action.get_action_url(ctx)}"' in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_get_of_a_form_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="edit-fragment-fetch")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    assign_perm("freedom_ls_panel_framework.change_stubmodel", request.user, item)

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert "hx-post=" in content
    assert "autofocus" in content


# -- DeleteAction tests --------------------------------------------------


@pytest.mark.django_db
def test_delete_action_handle_submit_deletes_and_redirects(
    mock_site_context: Site,
) -> None:
    """A successful delete with a success_url answers 204 with closeModal and
    HX-Location to success_url, never HX-Redirect. It sends no domain events:
    the page it leaves would hear them before the navigation and refetch
    panels scoped to the row that no longer exists."""
    item = _make_stub(name="to-delete")
    item_pk = item.pk
    action = DeleteAction(success_url="/items", success_events=("itemChanged",))

    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger({}, close_modal=True)
    assert json.loads(response["HX-Location"]) == {
        "path": "/items",
        "target": "#main-content",
        "swap": "outerHTML",
    }
    assert "HX-Redirect" not in response
    assert not StubModel.objects.filter(pk=item_pk).exists()


@pytest.mark.django_db
def test_delete_action_without_a_success_url_sends_its_events_and_stays_put(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="to-delete-in-place")
    item_pk = item.pk
    action = DeleteAction(success_events=("itemChanged",))

    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger(
        {"itemChanged": [str(item_pk)]}, close_modal=True
    )
    assert "HX-Location" not in response
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
def test_delete_action_cascade_summary_uses_the_singular_for_one_row(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="single-child-parent")
    _make_stub_child(parent=item)

    summary = DeleteAction(success_url="/items").get_cascade_summary(item)

    assert summary == ["1 stub child"]


@pytest.mark.django_db
def test_delete_action_cascade_summary_counts_fast_deleted_rows(
    mock_site_context: Site,
) -> None:
    """Rows Django bulk-deletes without loading them still appear in the summary.

    StubGrandchild has no dependents of its own, so the Collector fast-deletes
    it rather than putting it in ``Collector.data``.
    """
    item = _make_stub(name="fast-delete-parent")
    child = _make_stub_child(parent=item)
    for _ in range(3):
        StubGrandchild.objects.create(parent=child)

    summary = DeleteAction(success_url="/items").get_cascade_summary(item)

    assert "3 stub grandchilds" in summary


@pytest.mark.django_db
def test_delete_action_render_returns_confirmation_html(
    mock_site_context: Site,
) -> None:
    """Rendered delete confirmation includes delete button and action URL."""
    item = _make_stub(name="delete-render")
    action = DeleteAction(success_url="/items")

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    html = _render(action, _ctx(request, item))
    assert "Delete" in html
    assert "/test/__actions/delete" in html


@pytest.mark.django_db
def test_delete_action_has_permission_reflects_the_configs_answer(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="delete-permission-check")
    action = DeleteAction(success_url="/items")

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = _ctx(request, item)

    RecordingCapabilityConfig.reset(answer=True)
    assert action.has_permission(ctx) is True

    RecordingCapabilityConfig.reset(answer=False)
    assert action.has_permission(ctx) is False


@pytest.mark.django_db
def test_delete_action_permission_denied_raises_for_a_plain_request(
    mock_site_context: Site,
) -> None:
    """A plain (non-htmx) denial raises PermissionDenied, so the site's own
    403 page renders."""
    RecordingCapabilityConfig.reset(answer=False)
    item = _make_stub(name="delete-403")
    action = DeleteAction(success_url="/items")

    user = make_staff_user()
    request = RequestFactory().delete("/")
    request.user = user

    resolved = _ResolvedAction(action, _ctx(request, item))
    with pytest.raises(PermissionDenied):
        _handle_action(request, resolved)
    assert StubModel.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_delete_action_render_explains_a_protected_instance(
    mock_site_context: Site,
) -> None:
    """A protected instance renders an explanation, not a ProtectedError."""
    item = _make_stub(name="protected-render")
    _make_stub_protected_child(parent=item)
    action = DeleteAction(success_url="/items")

    request = RequestFactory().get("/")
    request.user = make_staff_user()

    html = _render(action, _ctx(request, item))
    assert "cannot be deleted" in html
    assert "stub protected child" in html.lower()
    # No live delete affordance: the submit would only fail the same way.
    assert "hx-delete" not in html


@pytest.mark.django_db
def test_delete_action_handle_submit_refuses_a_protected_instance(
    mock_site_context: Site,
) -> None:
    """Submitting a blocked delete returns the explanation, not a 500."""
    item = _make_stub(name="protected-submit")
    _make_stub_protected_child(parent=item)
    action = DeleteAction(success_url="/items")

    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))
    assert response.status_code == 422
    assert "cannot be deleted" in response.content.decode()
    assert StubModel.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_rendering_a_panel_with_a_delete_action_never_builds_a_cascade_summary(
    mock_site_context: Site, mocker: MockerFixture
) -> None:
    """Rendering a panel renders the action's trigger, never its fragment:
    the cascade summary is deferred to a GET of the action's own URL."""
    item = _make_stub(name="lazy-delete")
    action = DeleteAction(success_url="/items")
    get_cascade_summary = mocker.patch.object(DeleteAction, "get_cascade_summary")

    class PanelWithDelete(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [action]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    assign_perm("freedom_ls_panel_framework.delete_stubmodel", request.user, item)
    ctx = _ctx(request, item)
    html = _render_panel(PanelWithDelete(ctx))

    get_cascade_summary.assert_not_called()
    assert f'hx-get="{action.get_action_url(ctx)}"' in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_get_of_a_delete_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    item = _make_stub(name="delete-fragment-fetch")
    action = DeleteAction(success_url="/items")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    assign_perm("freedom_ls_panel_framework.delete_stubmodel", request.user, item)

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert "hx-delete=" in content


# -- Read-only PanelAction tests ------------------------------------------


@pytest.mark.django_db
def test_a_get_of_a_read_only_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    """A read-only action's fragment carries the shared modal heading, no
    form, and focuses itself since there is no field to autofocus instead."""
    item = _make_stub(name="read-only-fetch")
    action = StubReadOnlyAction()
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert 'tabindex="-1"' in content
    assert "autofocus" in content
    assert "<form" not in content
