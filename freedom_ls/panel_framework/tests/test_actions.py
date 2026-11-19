"""Tests for the panel actions: create, edit, delete and read-only, their
permission checks, the htmx responses they send and the modal fragments they render."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import cast

import lxml.html
import pytest

from django import forms
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Model, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory

from freedom_ls.panel_framework.actions import (
    CHOOSE_AGAIN_MESSAGE,
    ConfirmAction,
    CreateInstanceAction,
    DeleteAction,
    EditableListAddAction,
    EditableListEditAction,
    EditAction,
    FormPanelAction,
    PanelAction,
    ReasonMixin,
    changed_response,
    count_noun,
    current_page_within,
    form_fragment_context,
    join_prose,
    navigation_response,
    refusal_response,
)
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.events import build_hx_trigger
from freedom_ls.panel_framework.forms import REASON_LENGTH, ReasonForm
from freedom_ls.panel_framework.panels import Panel
from freedom_ls.panel_framework.views import (
    SectionConfigBase,
    _handle_action,
    _ResolvedAction,
)
from freedom_ls.panel_framework.widgets import PanelClearableFileInput

from .helpers import (
    make_staff_user,
    make_stub,
    make_stub_child,
    make_stub_entry,
    make_stub_entry_protected_child,
    make_stub_file,
    make_stub_protected_child,
)
from .stub_models import StubEntry, StubFileModel, StubGrandchild, StubModel
from .stub_panels import (
    RecordingCapabilityConfig,
    StubCappedEditableListPanel,
    StubEditableListPanel,
    StubReadOnlyAction,
)
from .view_helpers import fetch

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

    def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
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


class StubUnofferedAction(StubAction):
    action_name = "unoffered"
    label = "Hidden Thing"

    def is_offered(self, ctx: PanelContext) -> bool:
        return False


def test_an_action_is_offered_by_default() -> None:
    assert StubAction().is_offered(_ctx(RequestFactory().get("/"))) is True


def test_an_action_that_is_permitted_but_not_offered_is_not_available() -> None:
    ctx = _ctx(RequestFactory().get("/"))

    assert StubUnofferedAction().has_permission(ctx) is True
    assert StubUnofferedAction().is_available(ctx) is False


@pytest.mark.django_db
def test_an_action_that_is_not_offered_is_left_out_of_the_panel_actions(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="unoffered")

    class PanelWithActions(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [StubAction(), StubUnofferedAction()]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    panel = PanelWithActions(_ctx(request, item))

    actions = panel.get_context_data()["actions"]

    assert [action.action_name for action in actions] == ["do_thing"]


class StubRowAction(StubAction):
    action_name = "per_row"
    label = "Per Row"
    renders_in_footer = False


@pytest.mark.django_db
def test_a_row_action_is_kept_out_of_the_footer_and_exposed_by_url(
    mock_site_context: Site,
) -> None:
    """A row-scoped action resolves on the panel like any other, but the
    panel hands its URL to the cell templates instead of rendering it."""
    item = make_stub(name="rows")

    class PanelWithRowAction(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [StubAction(), StubRowAction()]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    context = PanelWithRowAction(_ctx(request, item)).get_context_data()

    assert [action.action_name for action in context["actions"]] == ["do_thing"]
    assert context["row_action_urls"] == {"per_row": "/test/__actions/per_row"}


@pytest.mark.django_db
def test_an_unavailable_row_action_has_no_url(mock_site_context: Site) -> None:
    item = make_stub(name="rows")

    class StubUnofferedRowAction(StubRowAction):
        def is_offered(self, ctx: PanelContext) -> bool:
            return False

    class PanelWithRowAction(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [StubUnofferedRowAction()]

    request = RequestFactory().get("/")
    request.user = make_staff_user()

    assert (
        PanelWithRowAction(_ctx(request, item)).get_context_data()["row_action_urls"]
        == {}
    )


class StubScopedRowAction(StubRowAction):
    row_param = "item"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Model]:
        return cast(QuerySet[Model], StubModel.objects.filter(is_active=True))


def _row_ctx(method: str, data: dict[str, str]) -> PanelContext:
    factory = RequestFactory()
    request = factory.post("/", data) if method == "POST" else factory.get("/", data)
    return _ctx(request)


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["GET", "POST"])
def test_get_row_object_returns_the_row_the_parameter_names(
    mock_site_context: Site, method: str
) -> None:
    item = make_stub()

    row = StubScopedRowAction().get_row_object(_row_ctx(method, {"item": str(item.pk)}))

    assert row == item


@pytest.mark.django_db
def test_get_row_object_reads_the_row_once_per_request(
    mock_site_context: Site, django_assert_max_num_queries
) -> None:
    item = make_stub()
    action = StubScopedRowAction()
    ctx = _row_ctx("GET", {"item": str(item.pk)})
    action.get_row_object(ctx)

    with django_assert_max_num_queries(0):
        row = action.get_row_object(ctx)

    assert row == item


@pytest.mark.django_db
@pytest.mark.parametrize("data", [{}, {"item": "not-a-number"}])
def test_get_row_object_is_a_404_for_a_missing_or_malformed_parameter(
    mock_site_context: Site, data: dict[str, str]
) -> None:
    make_stub()

    with pytest.raises(Http404):
        StubScopedRowAction().get_row_object(_row_ctx("GET", data))


@pytest.mark.django_db
def test_get_row_object_is_a_404_for_a_row_outside_the_queryset(
    mock_site_context: Site,
) -> None:
    item = make_stub(is_active=False)

    with pytest.raises(Http404):
        StubScopedRowAction().get_row_object(_row_ctx("GET", {"item": str(item.pk)}))


def test_get_row_object_without_a_row_param_is_misconfigured() -> None:
    with pytest.raises(ImproperlyConfigured):
        StubRowAction().get_row_object(_row_ctx("GET", {"item": "1"}))


def test_get_row_queryset_has_no_default() -> None:
    with pytest.raises(NotImplementedError):
        StubRowAction().get_row_queryset(_row_ctx("GET", {}))


def test_navigation_response_closes_the_modal_and_relocates_the_main_content() -> None:
    response = navigation_response("/items/1")

    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger({}, close_modal=True)
    assert json.loads(response["HX-Location"]) == {
        "path": "/items/1",
        "target": "#main-content",
        "swap": "outerHTML",
    }


@pytest.mark.parametrize(
    "current",
    [
        "http://testserver/cohorts/1/courses?page=2",
        # Only the path is used, so the host the browser saw is irrelevant.
        "http://public.example/cohorts/1/courses",
        "//public.example/cohorts/1/courses",
    ],
)
def test_current_page_within_returns_the_path_the_request_came_from(
    current: str,
) -> None:
    request = RequestFactory().post("/x", HTTP_HX_CURRENT_URL=current)

    assert current_page_within(request, "/cohorts/1") == "/cohorts/1/courses"


@pytest.mark.parametrize(
    "current",
    [
        "http://testserver/cohorts/10",
        "http://testserver/other",
        "",
    ],
)
def test_current_page_within_falls_back_to_the_root(current: str) -> None:
    request = RequestFactory().post("/x", HTTP_HX_CURRENT_URL=current)

    assert current_page_within(request, "/cohorts/1") == "/cohorts/1"


def test_changed_response_closes_the_modal_and_fires_the_events() -> None:
    response = changed_response({"thingChanged": ["1", "2"]})

    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger(
        {"thingChanged": ["1", "2"]}, close_modal=True
    )


@pytest.mark.django_db
def test_count_noun_uses_the_singular_for_one_and_the_plural_otherwise(
    mock_site_context: Site,
) -> None:
    assert count_noun(StubModel, 1) == "1 stub model"
    assert count_noun(StubModel, 3) == "3 stub models"


def test_join_prose_runs_parts_into_a_sentence() -> None:
    assert join_prose([]) == ""
    assert join_prose(["a"]) == "a"
    assert join_prose(["a", "b"]) == "a and b"
    assert join_prose(["a", "b", "c"]) == "a, b and c"


@pytest.mark.django_db
def test_panel_get_actions_returns_empty_list_by_default(
    mock_site_context: Site,
) -> None:
    """Panel.get_actions() returns empty list by default."""
    item = make_stub(name="test-item")
    panel = StubPanel(_ctx(RequestFactory().get("/"), item))
    assert panel.get_actions() == []


@pytest.mark.django_db
def test_panel_action_render_returns_button_html(mock_site_context: Site) -> None:
    """PanelAction renders its button through its trigger template."""
    item = make_stub(name="action-render")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    ctx = _ctx(request, item, "/test/base")
    action = StubAction()
    html = render_to_string(
        action.trigger_template_name, action.get_trigger_context(ctx), request=request
    )
    assert "Do Thing" in html


def test_panel_action_url_hangs_off_its_owners_base_url() -> None:
    context = StubAction().get_context_data(
        _ctx(RequestFactory().get("/"), None, "/a/b")
    )
    assert context["action_url"] == "/a/b/__actions/do_thing"


@pytest.mark.django_db
def test_panel_container_renders_actions_when_present(mock_site_context: Site) -> None:
    """Panel container renders action buttons when actions exist."""
    item = make_stub(name="actions-present")

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
    item = make_stub(name="no-actions")
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
    scope = make_stub(name="list-scope")
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
    instance = make_stub(name="instance-scope")
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
    item = make_stub(name="default-deny")
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
    scope = make_stub(name="delete-no-instance-scope")
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
    """ "Add" creates the instance and answers 204 with HX-Location, never
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
def test_create_action_add_another_returns_empty_form_status_and_trigger(
    mock_site_context: Site,
) -> None:
    """'Add and add another' returns 200 with the blank form, a sentence naming
    what was added and the domain event, and never closes the modal."""
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Item A", "action": "add_another"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    assert response.status_code == 200
    item = StubModel.objects.get(name="Item A")
    assert response["HX-Trigger"] == build_hx_trigger({"itemChanged": [str(item.pk)]})
    assert "HX-Location" not in response
    assert "HX-Redirect" not in response
    content = response.content.decode()
    assert "Create Item" in content
    assert f"Added {item}." in content


@pytest.mark.django_db
def test_create_action_posting_the_retired_value_adds_and_navigates(
    mock_site_context: Site,
) -> None:
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Item B", "action": "save_and_add"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    item = StubModel.objects.get(name="Item B")
    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger(
        {"itemChanged": [str(item.pk)]}, close_modal=True
    )


def test_create_action_offers_add_and_add_another_then_add() -> None:
    labels = [button["label"] for button in StubCreateAction().submit_buttons]

    assert labels == ["Add and add another", "Add"]


@pytest.mark.django_db
def test_add_another_response_stays_open_with_an_unbound_form_and_a_status(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().post("/", {"name": "Item C", "action": "add_another"})
    request.user = make_staff_user()

    response = StubCreateAction().add_another_response(
        _ctx(request, None, "/items"), {"itemChanged": ["7"]}, "Added Item C."
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert response["HX-Trigger"] == build_hx_trigger({"itemChanged": ["7"]})
    assert "Added Item C." in content
    assert 'value="Item C"' not in content


@pytest.mark.django_db
def test_a_create_action_on_an_instance_page_opens_an_empty_form(
    mock_site_context: Site,
) -> None:
    page_object = make_stub(name="Page object")

    form = StubCreateAction().get_form(_ctx(RequestFactory().get("/"), page_object))

    assert cast(forms.ModelForm, form).instance.pk is None


@pytest.mark.django_db
def test_a_create_action_on_an_instance_page_leaves_the_page_object_alone(
    mock_site_context: Site,
) -> None:
    page_object = make_stub(name="Page object")
    request = RequestFactory().post("/", {"name": "New Item"})
    request.user = make_staff_user()

    StubCreateAction().handle_submit(_ctx(request, page_object, "/items"))

    assert sorted(StubModel.objects.values_list("name", flat=True)) == [
        "New Item",
        "Page object",
    ]


@pytest.mark.django_db
def test_create_action_duplicate_name_returns_422(mock_site_context: Site) -> None:
    """Duplicate name within site returns 422 with validation error."""
    make_stub(name="Existing")
    action = StubCreateAction()
    request = RequestFactory().post("/", {"name": "Existing"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))
    assert response.status_code == 422
    content = response.content.decode()
    assert "data-error-summary" in content
    assert 'aria-invalid="true"' in content


class _FormLevelErrorForm(_StubModelForm):
    def clean(self) -> dict[str, object]:
        raise forms.ValidationError("These values cannot be combined.")


class StubFormLevelErrorCreateAction(StubCreateAction):
    form_class = _FormLevelErrorForm


@pytest.mark.django_db
def test_error_summary_does_not_count_a_form_level_error_as_a_field(
    mock_site_context: Site,
) -> None:
    """A non-field error is shown, but no field is claimed to need fixing."""
    action = StubFormLevelErrorCreateAction()
    request = RequestFactory().post("/", {"name": "Anything"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    assert response.status_code == 422
    content = response.content.decode()
    assert "These values cannot be combined." in content
    assert "to fix" not in content


@pytest.mark.django_db
def test_a_form_level_error_is_announced_once(mock_site_context: Site) -> None:
    """The error summary shows a non-field error; the form below it does not repeat it."""
    action = StubFormLevelErrorCreateAction()
    request = RequestFactory().post("/", {"name": "Anything"})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, None, "/items"))

    content = response.content.decode()
    assert content.count('role="alert"') == 1
    assert content.count("These values cannot be combined.") == 1


class _PlainForm(forms.Form):
    name = forms.CharField()
    colour = forms.CharField(required=False)


class StubPlainFormAction(FormPanelAction):
    label = "Plain"
    action_name = "plain"
    form_class = _PlainForm
    form_title = "A plain form"
    refresh_on_change = ("colour",)
    saved: list[str] = []

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        self.saved.append(form.cleaned_data["name"])
        return HttpResponse("saved")


@pytest.mark.django_db
def test_a_form_action_over_a_plain_form_renders_its_title_and_fields(
    mock_site_context: Site,
) -> None:
    ctx = _ctx(RequestFactory().get("/"))

    html = _render(StubPlainFormAction(), ctx)

    assert "A plain form" in html
    assert 'name="name"' in html


@pytest.mark.django_db
def test_a_form_action_over_a_plain_form_rerenders_422_with_the_error_count(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().post("/", {"name": ""})

    response = StubPlainFormAction().handle_submit(_ctx(request))

    assert response.status_code == 422
    assert "1 field to fix" in response.content.decode()


def test_a_form_action_over_a_plain_form_calls_form_valid_with_ctx_and_form() -> None:
    request = RequestFactory().post("/", {"name": "Ada"})
    StubPlainFormAction.saved.clear()

    response = StubPlainFormAction().handle_submit(_ctx(request))

    assert response.content == b"saved"
    assert StubPlainFormAction.saved == ["Ada"]


@pytest.mark.django_db
def test_a_form_action_over_a_model_form_receives_the_instance(
    mock_site_context: Site,
) -> None:
    class ModelFormAction(FormPanelAction):
        action_name = "model"
        form_class = _StubModelForm

    item = make_stub(name="Existing")

    form = ModelFormAction().get_form(_ctx(RequestFactory().get("/"), item))

    assert cast(forms.ModelForm, form).instance == item


def test_a_refresh_on_change_field_carries_the_refresh_attributes() -> None:
    ctx = _ctx(RequestFactory().get("/"), base_url="/test")

    form = StubPlainFormAction().get_form(ctx)

    attrs = form.fields["colour"].widget.attrs
    assert attrs["hx-get"] == "/test/__actions/plain"
    assert attrs["hx-target"] == "#app-modal-body"
    assert "hx-get" not in form.fields["name"].widget.attrs


def test_a_get_carrying_a_refresh_field_renders_the_form_bound_without_errors() -> None:
    ctx = _ctx(RequestFactory().get("/", {"name": "Ada", "colour": "red"}))

    form = StubPlainFormAction().get_form(ctx)

    assert form.is_bound
    assert not form.errors


def test_a_get_carrying_a_refresh_field_with_an_invalid_query_renders_unbound() -> None:
    ctx = _ctx(RequestFactory().get("/", {"colour": "red"}))

    form = StubPlainFormAction().get_form(ctx)

    assert not form.is_bound


@pytest.mark.django_db
def test_create_action_get_success_url_receives_ctx(mock_site_context: Site) -> None:
    class CtxUrlAction(StubCreateAction):
        def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
            return f"{ctx.base_url}/{instance.pk}"

    request = RequestFactory().post("/", {"name": "Ctx Item"})
    request.user = make_staff_user()

    response = CtxUrlAction().handle_submit(_ctx(request, None, "/here"))

    item = StubModel.objects.get(name="Ctx Item")
    assert json.loads(response["HX-Location"])["path"] == f"/here/{item.pk}"


@pytest.mark.django_db
def test_create_action_has_permission_reflects_the_configs_answer(
    mock_site_context: Site,
) -> None:
    action = StubCreateAction()
    item = make_stub(name="create-permission-check")
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
    scope = make_stub(name="create-403-scope")
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
    scope = make_stub(name="create-403-htmx-scope")
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
    assert "Create Item" in html
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
    item = make_stub(name="Old Name")
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


class _LabelledConfig(RecordingCapabilityConfig):
    """A section whose instances are named by something other than str()."""

    @classmethod
    def get_instance_label(cls, instance: Model) -> str:
        return f"Item {instance.name}"


@pytest.mark.django_db
def test_edit_action_names_the_new_title_the_way_its_section_does(
    mock_site_context: Site,
) -> None:
    """The page heading comes from the section's get_instance_label, so the
    title a save sends back must too, or the heading changes shape after a
    rename."""
    item = make_stub(name="Old Name")
    action = EditAction(
        form_class=_StubModelForm,
        form_title="Edit Item",
        instance=item,
        success_events=("itemChanged",),
    )
    request = RequestFactory().post("/", {"name": "New Name"})
    request.user = make_staff_user()
    ctx = PanelContext(
        request=request,
        instance=item,
        base_url="/test",
        name="",
        config=_LabelledConfig,
    )

    response = action.handle_submit(ctx)

    assert response["HX-Trigger"] == build_hx_trigger(
        {"itemChanged": [str(item.pk)]}, close_modal=True, title="Item New Name"
    )


@pytest.mark.django_db
def test_edit_action_duplicate_name_returns_422(mock_site_context: Site) -> None:
    """Duplicate name returns 422 with validation error."""
    make_stub(name="Existing-edit")
    item = make_stub(name="Original")
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
    item = make_stub(name="edit-permission-check")
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
    item = make_stub(name="Test-edit-403")
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
    mock_site_context: Site,
) -> None:
    """Rendering a panel renders the action's trigger, never its fragment:
    building the form is deferred to a GET of the action's own URL."""
    item = make_stub(name="lazy-edit")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )

    class PanelWithEdit(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [action]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)
    ctx = _ctx(request, item)
    html = _render_panel(PanelWithEdit(ctx))

    assert f'hx-get="{action.get_action_url(ctx)}"' in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_get_of_a_form_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="edit-fragment-fetch")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    assert isinstance(response, HttpResponse)
    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert "hx-post=" in content
    assert "autofocus" in content


@pytest.mark.django_db
def test_the_form_fragment_posts_to_the_actions_url(mock_site_context: Site) -> None:
    item = make_stub(name="edit-fragment-action-url")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)
    ctx = _ctx(request, item)

    response = _handle_action(request, _ResolvedAction(action, ctx))

    assert isinstance(response, HttpResponse)
    (form,) = lxml.html.fromstring(response.content.decode()).cssselect("form")
    assert form.get("hx-post") == action.get_action_url(ctx)


def test_a_get_of_an_action_with_no_template_name_is_not_allowed() -> None:
    request = RequestFactory().get("/")
    RecordingCapabilityConfig.reset(answer=True)
    resolved = _ResolvedAction(StubAction(), _ctx(request))

    response = _handle_action(request, resolved)

    assert isinstance(response, HttpResponse)
    assert response.status_code == 405
    assert response["Allow"] == "POST"


def test_an_action_with_no_template_name_has_no_fragment_template() -> None:
    with pytest.raises(ImproperlyConfigured, match="StubAction"):
        StubAction().get_fragment_template_name()


@pytest.mark.django_db
def test_the_form_fragment_has_a_header_with_close_before_a_form_with_cancel_then_submit(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="edit-fragment-structure")
    action = EditAction(
        form_class=_StubModelForm, form_title="Edit Item", instance=item
    )
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)

    response = _handle_action(request, _ResolvedAction(action, _ctx(request, item)))

    assert isinstance(response, HttpResponse)
    document = lxml.html.fromstring(response.content.decode())
    (heading,) = document.cssselect("#app-modal-title")
    assert heading.getparent().tag == "header"
    labels = [
        el.get("aria-label") or el.text_content().strip()
        for el in document.iter("button")
    ]
    assert labels.index("Close") < labels.index("Cancel")
    form_buttons = document.cssselect("form button")
    assert form_buttons[0].text_content().strip() == "Cancel"
    assert form_buttons[-1].get("type") == "submit"


# -- DeleteAction tests --------------------------------------------------


@pytest.mark.django_db
def test_delete_action_handle_submit_deletes_and_redirects(
    mock_site_context: Site,
) -> None:
    """A successful delete with a success_url answers 204 with closeModal and
    HX-Location to success_url, never HX-Redirect. It sends no domain events:
    the page it leaves would hear them before the navigation and refetch
    panels scoped to the row that no longer exists."""
    item = make_stub(name="to-delete")
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
    item = make_stub(name="to-delete-in-place")
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
    item = make_stub(name="cascade-parent")
    make_stub_child(parent=item)
    make_stub_child(parent=item)

    action = DeleteAction(success_url="/items")
    summary = action.get_cascade_summary(item)
    assert len(summary) > 0
    summary_text = " ".join(summary).lower()
    assert "stub child" in summary_text


@pytest.mark.django_db
def test_delete_action_cascade_summary_uses_the_singular_for_one_row(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="single-child-parent")
    make_stub_child(parent=item)

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
    item = make_stub(name="fast-delete-parent")
    child = make_stub_child(parent=item)
    for _ in range(3):
        StubGrandchild.objects.create(parent=child)

    summary = DeleteAction(success_url="/items").get_cascade_summary(item)

    assert "3 stub grandchilds" in summary


@pytest.mark.django_db
def test_a_refusal_from_before_delete_is_answered_and_keeps_the_row(
    mock_site_context: Site,
) -> None:
    class _RefusingDelete(DeleteAction):
        def before_delete(self, ctx: PanelContext, instance: Model) -> HttpResponse:
            return self._blocked_response(ctx, instance, "Not today.")

    item = make_stub(name="kept")
    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = _RefusingDelete(success_url="/items").handle_submit(_ctx(request, item))

    assert response.status_code == 422
    assert "Not today." in response.content.decode()
    assert StubModel.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_delete_action_render_returns_confirmation_html(
    mock_site_context: Site,
) -> None:
    """Rendered delete confirmation includes delete button and action URL."""
    item = make_stub(name="delete-render")
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
    item = make_stub(name="delete-permission-check")
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
    item = make_stub(name="delete-403")
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
    item = make_stub(name="protected-render")
    make_stub_protected_child(parent=item)
    action = DeleteAction(success_url="/items")

    request = RequestFactory().get("/")
    request.user = make_staff_user()

    html = _render(action, _ctx(request, item))
    assert "cannot be deleted" in html
    assert "stub protected child" in html.lower()
    # No live delete affordance: the submit would only fail the same way.
    document = lxml.html.fromstring(html)
    assert not document.cssselect("button[type='submit']")
    assert document.cssselect("[data-error-summary][tabindex='-1'][role='alert']")


@pytest.mark.django_db
def test_delete_action_handle_submit_refuses_a_protected_instance(
    mock_site_context: Site,
) -> None:
    """Submitting a blocked delete returns the explanation, not a 500."""
    item = make_stub(name="protected-submit")
    make_stub_protected_child(parent=item)
    action = DeleteAction(success_url="/items")

    request = RequestFactory().delete("/")
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))
    assert response.status_code == 422
    assert "cannot be deleted" in response.content.decode()
    assert StubModel.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_a_refused_delete_renders_the_reason_as_the_error_summary(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="refused-summary")
    make_stub_protected_child(parent=item)
    request = RequestFactory().post("/")
    request.user = make_staff_user()

    response = DeleteAction(success_url="/items").handle_submit(_ctx(request, item))

    document = lxml.html.fromstring(response.content.decode())
    (summary,) = document.cssselect("[data-error-summary]")
    assert summary.get("tabindex") == "-1"
    assert summary.get("role") == "alert"
    assert "cannot be deleted" in summary.text_content()


@pytest.mark.django_db
def test_delete_action_deletes_on_post(mock_site_context: Site) -> None:
    item = make_stub(name="post-delete")
    request = RequestFactory().post("/")
    request.user = make_staff_user()

    response = DeleteAction(success_url="/items").handle_submit(_ctx(request, item))

    assert response.status_code == 204
    assert not StubModel.objects.filter(pk=item.pk).exists()


class StubRecordingDelete(DeleteAction):
    """Records every cascade collection, which walks every related row."""

    def __init__(self, known_reason: str = "") -> None:
        super().__init__(success_url="/items")
        self.known_reason = known_reason
        self.collected: list[Model] = []

    def get_cascade_summary(self, instance: Model) -> list[str]:
        self.collected.append(instance)
        return super().get_cascade_summary(instance)

    def get_known_blocked_reason(self, ctx: PanelContext, instance: Model) -> str:
        return self.known_reason


@pytest.mark.django_db
def test_a_delete_refused_by_a_protected_row_does_not_collect_the_cascade_again(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="protected-no-recollect")
    make_stub_protected_child(parent=item)
    action = StubRecordingDelete()
    request = RequestFactory().post("/")
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 422
    assert action.collected == []


@pytest.mark.django_db
def test_a_delete_with_a_known_blocked_reason_shows_it_without_collecting(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="known-reason")
    make_stub_child(parent=item)
    action = StubRecordingDelete(known_reason="This item is still in use.")
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    document = lxml.html.fromstring(_render(action, _ctx(request, item)))

    (summary,) = document.cssselect("[data-error-summary]")
    assert "This item is still in use." in summary.text_content()
    assert not document.cssselect("button[type='submit']")
    assert action.collected == []


@pytest.mark.django_db
def test_a_delete_with_no_known_blocked_reason_lists_its_cascade(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="no-known-reason")
    make_stub_child(parent=item)
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    html = _render(StubRecordingDelete(), _ctx(request, item))

    assert "1 stub child" in html.lower()


class StubReasonDelete(ReasonMixin, DeleteAction):
    pass


@pytest.mark.django_db
def test_a_reason_delete_carries_the_reason_to_the_context(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="reason-delete")
    seen: list[str] = []

    class RecordingDelete(StubReasonDelete):
        def before_delete(self, ctx: PanelContext, instance: Model) -> None:
            seen.append(ctx.reason)

    request = RequestFactory().post("/", {"reason": " Merged "})
    request.user = make_staff_user()

    response = RecordingDelete(success_url="/items").handle_submit(_ctx(request, item))

    assert response.status_code == 204
    assert seen == ["Merged"]


@pytest.mark.django_db
def test_a_blocked_reason_delete_keeps_the_reason_field_out_of_the_dialog(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="blocked-reason-delete")
    make_stub_protected_child(parent=item)
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    html = _render(StubReasonDelete(success_url="/items"), _ctx(request, item))

    assert not lxml.html.fromstring(html).cssselect("input[name='reason']")


@pytest.mark.django_db
def test_rendering_a_panel_with_a_delete_action_never_builds_a_cascade_summary(
    mock_site_context: Site,
) -> None:
    """Rendering a panel renders the action's trigger, never its fragment:
    the cascade summary is deferred to a GET of the action's own URL."""
    item = make_stub(name="lazy-delete")
    action = DeleteAction(success_url="/items")

    class PanelWithDelete(StubPanel):
        def get_actions(self) -> list[PanelAction]:
            return [action]

    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)
    ctx = _ctx(request, item)
    html = _render_panel(PanelWithDelete(ctx))

    assert f'hx-get="{action.get_action_url(ctx)}"' in html
    assert "<form" not in html


@pytest.mark.django_db
def test_a_get_of_a_delete_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="delete-fragment-fetch")
    action = DeleteAction(success_url="/items")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    assert isinstance(response, HttpResponse)
    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert "hx-post=" in content


@pytest.mark.django_db
def test_the_delete_fragment_lists_cancel_then_delete_after_its_body(
    mock_site_context: Site,
) -> None:
    item = make_stub(name="delete-fragment-structure")
    action = DeleteAction(success_url="/items")
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    RecordingCapabilityConfig.reset(answer=True)

    response = _handle_action(request, _ResolvedAction(action, _ctx(request, item)))

    assert isinstance(response, HttpResponse)
    document = lxml.html.fromstring(response.content.decode())
    (heading,) = document.cssselect("#app-modal-title")
    assert heading.getparent().tag == "header"
    names = [
        el.text_content().split()[0]
        for el in document.iter("button")
        if el.text_content().strip()
    ]
    assert names[-2:] == ["Cancel", "Delete"]
    assert document.cssselect("form footer button[type='submit']")


class StubConfirmAction(ConfirmAction):
    label = "Archive"
    action_name = "stub_confirm"
    confirm_variant = "error"
    loading_text = "Archiving…"
    template_name = "panel_framework/test_confirm_dialog.html"

    def get_hidden_fields(self, ctx: PanelContext) -> dict[str, str]:
        return {"row": "7"}

    def get_confirm_context(self, ctx: PanelContext) -> dict[str, object]:
        return {
            "refusal": ctx.request.GET.get("refusal", ""),
            "confirm_disabled_reason": ctx.request.GET.get("disabled", ""),
            "page_url": ctx.request.GET.get("page_url", ""),
        }


class StubConfirmReasonAction(ReasonMixin, StubConfirmAction):
    pass


class StubRowConfirmAction(ConfirmAction):
    label = "Archive"
    action_name = "stub_row_confirm"
    row_param = "item"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Model]:
        return cast(QuerySet[Model], StubModel.objects.all())


@pytest.mark.django_db
def test_a_row_confirm_posts_its_row_back_as_a_hidden_field(
    mock_site_context: Site,
) -> None:
    item = make_stub()
    ctx = _row_ctx("GET", {"item": str(item.pk)})

    assert StubRowConfirmAction().get_hidden_fields(ctx) == {"item": str(item.pk)}


def test_a_confirm_with_no_row_has_no_hidden_fields() -> None:
    class PageConfirmAction(ConfirmAction):
        label = "Archive"

    assert PageConfirmAction().get_hidden_fields(_row_ctx("GET", {})) == {}


def _render_confirm(action: ConfirmAction, **query: str) -> lxml.html.HtmlElement:
    request = RequestFactory().get("/", query)
    request.user = make_staff_user()
    return lxml.html.fromstring(_render(action, _ctx(request)))


@pytest.mark.django_db
def test_a_confirm_dialog_renders_its_title_body_and_hidden_fields(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction())

    assert document.get_element_by_id("app-modal-title").text_content() == "Archive"
    assert "Archive this item?" in document.text_content()
    (hidden,) = document.cssselect("form input[type='hidden'][name='row']")
    assert hidden.get("value") == "7"
    assert document.cssselect("input[name='csrfmiddlewaretoken']")


@pytest.mark.django_db
def test_a_confirm_dialog_has_one_confirm_button_inside_a_form_wrapping_body_and_footer(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction())

    (form,) = document.cssselect("form[hx-post='/test/__actions/stub_confirm']")
    assert form.get("action") == "/test/__actions/stub_confirm"
    assert form.cssselect("#stub-confirm-body")
    assert form.cssselect("footer")
    (confirm,) = document.cssselect("button[type='submit']")
    assert confirm.cssselect("span")[0].text_content().strip() == "Archive"
    assert confirm.get("data-variant") == "error"
    assert "Archiving…" in confirm.text_content()


@pytest.mark.django_db
def test_a_confirm_dialog_with_a_reason_holds_the_field_inside_its_body(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmReasonAction())

    (field,) = document.cssselect("form input[name='reason']")
    body = document.cssselect("#stub-confirm-body")[0].getparent()
    assert body in field.iterancestors()


@pytest.mark.django_db
def test_a_confirm_dialog_shows_a_refusal_as_an_error_notice(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction(), refusal="Not open any more.")

    (notice,) = document.cssselect("[data-error-summary]")
    assert notice.get("role") == "alert"
    assert notice.get("tabindex") == "-1"
    assert "Not open any more." in notice.text_content()
    assert not _render_confirm(StubConfirmAction()).cssselect("[data-error-summary]")


@pytest.mark.django_db
def test_a_disabled_confirm_is_named_by_a_visible_reason_in_the_body(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction(), disabled="Pick one first.")

    (confirm,) = document.cssselect("footer button[type='submit']")
    assert confirm.get("disabled") is not None
    reason = document.get_element_by_id(confirm.get("aria-describedby"))
    assert reason.text_content() == "Pick one first."
    assert "sr-only" not in (reason.get("class") or "")
    assert document.cssselect("[data-modal-scroll] #confirm-disabled-reason")
    assert not document.cssselect("footer #confirm-disabled-reason")


@pytest.mark.django_db
def test_an_enabled_confirm_has_no_description_and_is_not_disabled(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction())

    (confirm,) = document.cssselect("footer button[type='submit']")
    assert confirm.get("disabled") is None
    assert confirm.get("aria-describedby") is None


@pytest.mark.django_db
def test_a_confirm_dialog_given_a_page_url_links_close_and_cancel_back_to_it(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction(), page_url="/test/page")

    links = [
        el.get("href")
        for el in document.iter("a")
        if el.get("aria-label") == "Close" or el.text_content().strip() == "Cancel"
    ]
    assert links == ["/test/page", "/test/page"]


@pytest.mark.django_db
def test_a_confirm_dialog_without_a_page_url_closes_through_the_dialog(
    mock_site_context: Site,
) -> None:
    document = _render_confirm(StubConfirmAction())

    assert not document.cssselect("header a, footer a")
    assert document.cssselect("footer button[x-on\\:click='cancel']")


@pytest.mark.django_db
def test_a_confirm_action_refuses_with_a_message_dialog(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().post("/")
    request.user = make_staff_user()

    response = StubConfirmAction().refuse(
        _ctx(request), "Nothing changed.", title="Already done"
    )

    assert response.status_code == 422
    assert "Already done" in response.content.decode()
    assert "Nothing changed." in response.content.decode()


# -- Read-only PanelAction tests ------------------------------------------


@pytest.mark.django_db
def test_a_get_of_a_read_only_actions_url_returns_its_fragment(
    mock_site_context: Site,
) -> None:
    """A read-only action's fragment carries the shared modal heading, no
    form, and a Close button that takes focus since there is no field to
    autofocus instead."""
    item = make_stub(name="read-only-fetch")
    action = StubReadOnlyAction()
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    resolved = _ResolvedAction(action, _ctx(request, item))
    response = _handle_action(request, resolved)

    assert isinstance(response, HttpResponse)
    content = response.content.decode()
    assert 'id="app-modal-title"' in content
    assert 'tabindex="-1"' not in content
    assert "autofocus" in content
    assert "<form" not in content


def test_a_form_fragment_can_leave_its_first_field_without_autofocus() -> None:
    """A form rendered as part of a page must not take focus on load."""
    form = forms.Form()
    form.fields["name"] = forms.CharField()

    context = form_fragment_context(
        form, form_title="t", action_url="/u", submit_buttons=[], autofocus=False
    )

    rendered = cast(forms.Form, context["form"])
    assert "autofocus" not in rendered.fields["name"].widget.attrs


# -- ReasonMixin tests ---------------------------------------------------


class StubReasonAction(ReasonMixin, ConfirmAction):
    label = "Archive"
    action_name = "stub_reason"
    template_name = "panel_framework/test_reason_dialog.html"

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        return HttpResponse(f"reason={ctx.reason}", status=200)


class StubWordedReasonForm(ReasonForm):
    reason_label = "Why archive?"
    reason_help_text = "Shown to admins."


class StubWordedReasonAction(StubReasonAction):
    reason_form_class = StubWordedReasonForm


@pytest.mark.django_db
def test_a_reason_dialog_renders_the_optional_reason_field(
    mock_site_context: Site,
) -> None:
    ctx = _ctx(RequestFactory().get("/"))

    document = lxml.html.fromstring(_render(StubReasonAction(), ctx))

    (field,) = document.cssselect("form input[name='reason']")
    assert field.get("maxlength") == "500"
    label = document.cssselect(f"label[for='{field.get('id')}']")[0]
    assert label.text_content().strip() == "Reason (optional):"


@pytest.mark.django_db
def test_a_reason_dialog_can_word_its_field_through_the_form_class(
    mock_site_context: Site,
) -> None:
    ctx = _ctx(RequestFactory().get("/"))

    content = _render(StubWordedReasonAction(), ctx)

    assert "Why archive?" in content
    assert "Shown to admins." in content


def test_a_blank_reason_submits() -> None:
    request = RequestFactory().post("/", {"reason": ""})

    response = StubReasonAction().handle_submit(_ctx(request))

    assert response.status_code == 200
    assert response.content == b"reason="


def test_a_reason_is_stripped_and_put_on_the_context() -> None:
    request = RequestFactory().post("/", {"reason": "  Left the programme  "})

    response = StubReasonAction().handle_submit(_ctx(request))

    assert response.content == b"reason=Left the programme"


@pytest.mark.django_db
def test_an_over_length_reason_is_a_422_with_the_field_re_rendered(
    mock_site_context: Site,
) -> None:
    too_long = "x" * (REASON_LENGTH + 1)
    request = RequestFactory().post("/", {"reason": too_long})

    response = StubReasonAction().handle_submit(_ctx(request))

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    (field,) = document.cssselect("form input[name='reason']")
    assert field.get("value") == too_long
    assert document.cssselect(".text-error")


class StubRequiredReasonAction(StubReasonAction):
    action_name = "stub_required_reason"
    reason_required = True


class StubChoiceReasonAction(StubReasonAction):
    action_name = "stub_choice_reason"
    reason_choices = [("moved", "Moved away"), ("other", "Other")]

    def handle_confirmed_submit(self, ctx: PanelContext) -> HttpResponse:
        return HttpResponse(f"choice={ctx.reason_choice};reason={ctx.reason}")


class StubRequiredChoiceReasonAction(StubChoiceReasonAction):
    reason_required = True


class StubComputedChoiceReasonAction(StubChoiceReasonAction):
    reason_choices = []

    def get_reason_choices(self, ctx: PanelContext) -> list[tuple[str, str]]:
        return [("computed", "Computed choice")]


class LegacyReasonForm(forms.Form):
    """A host form whose `__init__` takes only the data."""

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        super().__init__(data)
        self.fields["reason"] = forms.CharField(required=False)


class StubLegacyFormReasonAction(StubReasonAction):
    reason_form_class = cast(type[ReasonForm], LegacyReasonForm)


def _post_reason(action: ReasonMixin, data: dict[str, str]) -> HttpResponse:
    request = RequestFactory().post("/", data)
    request.user = make_staff_user()
    return action.handle_submit(_ctx(request))


@pytest.mark.django_db
def test_a_required_reason_posted_empty_is_a_422_with_the_error_under_the_field(
    mock_site_context: Site,
) -> None:
    response = _post_reason(StubRequiredReasonAction(), {"reason": ""})

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    assert document.cssselect("form input[name='reason'] ~ .text-error, .text-error")


@pytest.mark.django_db
def test_an_unknown_choice_is_a_422_that_keeps_the_typed_text(
    mock_site_context: Site,
) -> None:
    response = _post_reason(
        StubChoiceReasonAction(), {"reason_choice": "bogus", "reason": "typed text"}
    )

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    (field,) = document.cssselect("form input[name='reason']")
    assert field.get("value") == "typed text"
    assert document.cssselect(".text-error")


@pytest.mark.django_db
def test_a_valid_choice_with_missing_required_text_keeps_the_option_selected(
    mock_site_context: Site,
) -> None:
    response = _post_reason(
        StubRequiredChoiceReasonAction(), {"reason_choice": "moved", "reason": ""}
    )

    assert response.status_code == 422
    document = lxml.html.fromstring(response.content.decode())
    (selected,) = document.cssselect("select[name='reason_choice'] option[selected]")
    assert selected.get("value") == "moved"


@pytest.mark.django_db
def test_a_valid_post_reaches_the_submit_with_the_reason_and_the_choice(
    mock_site_context: Site,
) -> None:
    response = _post_reason(
        StubRequiredChoiceReasonAction(),
        {"reason_choice": "moved", "reason": "  new city "},
    )

    assert response.status_code == 200
    assert response.content == b"choice=moved;reason=new city"


@pytest.mark.django_db
def test_an_action_computing_its_choices_renders_and_validates_against_them(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    document = lxml.html.fromstring(
        _render(StubComputedChoiceReasonAction(), _ctx(request))
    )
    values = [
        option.get("value")
        for option in document.cssselect("select[name='reason_choice'] option")
    ]

    assert values == ["", "computed"]
    assert (
        _post_reason(
            StubComputedChoiceReasonAction(), {"reason_choice": "computed"}
        ).content
        == b"choice=computed;reason="
    )
    assert (
        _post_reason(StubComputedChoiceReasonAction(), {"reason_choice": "moved"})
    ).status_code == 422


@pytest.mark.django_db
def test_a_form_class_taking_only_the_data_still_renders_and_submits(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    document = lxml.html.fromstring(
        _render(StubLegacyFormReasonAction(), _ctx(request))
    )

    assert document.cssselect("form input[name='reason']")
    assert _post_reason(StubLegacyFormReasonAction(), {"reason": "x"}).content == (
        b"reason=x"
    )


def _refusal(**kwargs: object) -> HttpResponse:
    request = RequestFactory().post("/")
    request.user = make_staff_user()
    ctx = _ctx(request)
    return refusal_response(ctx, title="Not changed", message="It was.", **kwargs)


@pytest.mark.django_db
def test_refusal_response_is_a_422_by_default(mock_site_context: Site) -> None:
    assert _refusal().status_code == 422


@pytest.mark.django_db
def test_refusal_response_takes_the_given_status(mock_site_context: Site) -> None:
    assert _refusal(status=409).status_code == 409


@pytest.mark.django_db
def test_refusal_response_renders_the_title_the_message_and_a_focused_close(
    mock_site_context: Site,
) -> None:
    document = lxml.html.fromstring(_refusal().content.decode())

    assert document.get_element_by_id("app-modal-title").text_content() == "Not changed"
    assert "It was." in document.text_content()
    close = [
        el
        for el in document.iter("button")
        if el.text_content().strip() == "Close" and el.get("x-on:click") == "cancel"
    ]
    assert len(close) == 1
    assert close[0].get("autofocus") is not None
    assert document.get_element_by_id("app-modal-title").get("autofocus") is None


# -- File uploads --------------------------------------------------------


class _UploadForm(forms.Form):
    name = forms.CharField()
    attachment = forms.FileField()


class _StubFileModelForm(forms.ModelForm):
    class Meta:
        model = StubFileModel
        fields = ["name", "attachment"]


class StubUploadFormAction(FormPanelAction):
    label = "Upload"
    action_name = "upload"
    form_class = _UploadForm
    form_title = "Upload"
    received: list[forms.BaseForm] = []

    def form_valid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        self.received.append(form)
        return HttpResponse("saved")


class StubFileCreateAction(CreateInstanceAction):
    form_class = _StubFileModelForm
    form_title = "Create file record"
    label = "Create file record"
    action_name = "create_file_record"

    def get_success_url(self, ctx: PanelContext, instance: Model) -> str:
        return f"/files/{instance.pk}"


def _upload(content: bytes = b"hello", name: str = "notes.txt") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content)


def test_get_form_kwargs_passes_the_uploaded_files_on_a_post() -> None:
    request = RequestFactory().post("/", {"name": "Ada", "attachment": _upload()})

    kwargs = StubUploadFormAction().get_form_kwargs(_ctx(request))

    assert kwargs["files"] is request.FILES
    assert "attachment" in cast(dict[str, object], kwargs["files"])


def test_get_form_kwargs_passes_no_files_on_a_get() -> None:
    kwargs = StubUploadFormAction().get_form_kwargs(_ctx(RequestFactory().get("/")))

    assert kwargs["files"] is None
    assert kwargs["data"] is None


def test_get_unbound_form_on_a_multipart_post_is_unbound_for_data_and_files() -> None:
    request = RequestFactory().post("/", {"name": "Ada", "attachment": _upload()})

    form = StubUploadFormAction().get_unbound_form(_ctx(request))

    assert form.is_bound is False
    assert form.files == {}


def test_a_multipart_post_to_a_form_action_reaches_form_valid_with_the_file() -> None:
    request = RequestFactory().post(
        "/", {"name": "Ada", "attachment": _upload(b"payload")}
    )
    StubUploadFormAction.received.clear()

    response = StubUploadFormAction().handle_submit(_ctx(request))

    assert response.content == b"saved"
    (form,) = StubUploadFormAction.received
    assert form.cleaned_data["attachment"].read() == b"payload"


@pytest.mark.django_db
def test_a_multipart_post_to_an_edit_action_saves_the_file_on_the_instance(
    mock_site_context: Site,
) -> None:
    item = make_stub_file(name="Record")
    action = EditAction(form_class=_StubFileModelForm, form_title="Edit", instance=item)
    request = RequestFactory().post(
        "/", {"name": "Record", "attachment": _upload(b"payload")}
    )
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 204
    item.refresh_from_db()
    with item.attachment.open() as saved:
        assert saved.read() == b"payload"


@pytest.mark.django_db
def test_a_multipart_post_to_a_create_action_saves_the_file(
    mock_site_context: Site,
) -> None:
    request = RequestFactory().post(
        "/", {"name": "Fresh", "attachment": _upload(b"payload")}
    )
    request.user = make_staff_user()

    response = StubFileCreateAction().handle_submit(_ctx(request, None, "/files"))

    assert response.status_code == 204
    item = StubFileModel.objects.get(name="Fresh")
    with item.attachment.open() as saved:
        assert saved.read() == b"payload"


class _AcceptingFileForm(forms.ModelForm):
    class Meta:
        model = StubFileModel
        fields = ["name", "attachment"]
        widgets = {"attachment": forms.ClearableFileInput(attrs={"accept": ".pdf"})}


class _DeclaredFileInputForm(forms.Form):
    attachment = forms.FileField(widget=forms.FileInput)


class _AcceptingFileAction(FormPanelAction):
    action_name = "accepting"
    form_class = _AcceptingFileForm


class _DeclaredFileInputAction(FormPanelAction):
    action_name = "declared"
    form_class = _DeclaredFileInputForm


@pytest.mark.parametrize("build", ["get_form", "get_unbound_form"])
def test_a_file_field_gets_the_framework_widget_keeping_its_attrs_and_required(
    build: str,
) -> None:
    action = _AcceptingFileAction()
    form = getattr(action, build)(_ctx(RequestFactory().get("/")))

    widget = form.fields["attachment"].widget
    assert isinstance(widget, PanelClearableFileInput)
    assert widget.attrs["accept"] == ".pdf"
    assert widget.attrs is not _AcceptingFileForm.base_fields["attachment"].widget.attrs
    assert widget.is_required is form.fields["attachment"].required


def test_a_required_file_field_keeps_is_required_on_the_framework_widget() -> None:
    form = StubUploadFormAction().get_form(_ctx(RequestFactory().get("/")))

    widget = form.fields["attachment"].widget
    assert isinstance(widget, PanelClearableFileInput)
    assert widget.is_required is True


@pytest.mark.parametrize("build", ["get_form", "get_unbound_form"])
def test_a_declared_file_input_is_not_replaced(build: str) -> None:
    form = getattr(_DeclaredFileInputAction(), build)(_ctx(RequestFactory().get("/")))

    assert type(form.fields["attachment"].widget) is forms.FileInput


def _edit_file_record(
    post: dict[str, object],
) -> tuple[StubFileModel, HttpResponse]:
    item = make_stub_file(name="Record", attachment=_upload(b"old", "old.txt"))
    action = EditAction(form_class=_StubFileModelForm, form_title="Edit", instance=item)
    request = RequestFactory().post("/", post)
    request.user = make_staff_user()
    return item, action.handle_submit(_ctx(request, item))


@pytest.mark.django_db
def test_a_ticked_remove_clears_the_instances_file(mock_site_context: Site) -> None:
    item, response = _edit_file_record({"name": "Record", "attachment-clear": "on"})

    assert response.status_code == 204
    item.refresh_from_db()
    assert not item.attachment


@pytest.mark.django_db
def test_a_ticked_remove_comes_back_ticked_when_another_field_is_invalid(
    mock_site_context: Site,
) -> None:
    item, response = _edit_file_record({"name": "", "attachment-clear": "on"})

    assert response.status_code == 422
    root = lxml.html.fromstring(response.content.decode())
    (checkbox,) = root.xpath("//input[@name='attachment-clear']")
    assert checkbox.get("checked") is not None
    item.refresh_from_db()
    assert str(item.attachment.name).endswith("old.txt")


@pytest.mark.django_db
def test_a_ticked_remove_with_a_new_upload_is_a_contradiction(
    mock_site_context: Site,
) -> None:
    _, response = _edit_file_record(
        {"name": "Record", "attachment-clear": "on", "attachment": _upload()}
    )

    assert response.status_code == 422
    assert "not both" in response.content.decode().lower()


class _OverridingInvalidAction(StubUploadFormAction):
    action_name = "overriding_invalid"

    def form_invalid(self, ctx: PanelContext, form: forms.BaseForm) -> HttpResponse:
        return HttpResponse("\n".join(form.errors["attachment"]), status=422)


class _RejectingUploadForm(_UploadForm):
    def clean_attachment(self) -> object:
        raise forms.ValidationError("That file type is not allowed.")


class _RejectingUploadAction(StubUploadFormAction):
    action_name = "rejecting"
    form_class = _RejectingUploadForm


class _PrefixedUploadAction(StubUploadFormAction):
    action_name = "prefixed"

    def get_form_kwargs(self, ctx: PanelContext) -> dict[str, object]:
        return {**super().get_form_kwargs(ctx), "prefix": "doc"}


def _post_upload(
    action: FormPanelAction, post: dict[str, object]
) -> lxml.html.HtmlElement:
    request = RequestFactory().post("/", post)
    request.user = make_staff_user()
    response = action.handle_submit(_ctx(request))
    assert response.status_code == 422
    return lxml.html.fromstring(response.content.decode())


def _field_error_texts(root: lxml.html.HtmlElement) -> list[str]:
    return [item.text_content() for item in root.cssselect("ul.errorlist li")]


@pytest.mark.django_db
def test_a_422_with_a_file_chosen_asks_for_the_file_again(
    mock_site_context: Site,
) -> None:
    root = _post_upload(StubUploadFormAction(), {"name": "", "attachment": _upload()})

    (file_input,) = root.xpath("//input[@name='attachment']")
    assert file_input.get("value") is None
    assert CHOOSE_AGAIN_MESSAGE in _field_error_texts(root)
    summary = " ".join(root.xpath("//*[@data-error-summary]//text()"))
    assert "2 fields to fix." in summary


@pytest.mark.django_db
def test_a_422_on_an_edit_action_still_names_the_current_file(
    mock_site_context: Site,
) -> None:
    item = make_stub_file(name="Record", attachment=_upload(b"old", "old.txt"))
    action = EditAction(form_class=_StubFileModelForm, form_title="Edit", instance=item)
    request = RequestFactory().post("/", {"name": "", "attachment": _upload()})
    request.user = make_staff_user()

    response = action.handle_submit(_ctx(request, item))

    assert response.status_code == 422
    body = response.content.decode()
    assert "old.txt" in body
    assert CHOOSE_AGAIN_MESSAGE in body


@pytest.mark.django_db
def test_a_prefixed_form_gets_the_choose_again_message(mock_site_context: Site) -> None:
    root = _post_upload(
        _PrefixedUploadAction(), {"doc-name": "", "doc-attachment": _upload()}
    )

    assert CHOOSE_AGAIN_MESSAGE in _field_error_texts(root)


@pytest.mark.django_db
def test_a_file_field_with_its_own_error_shows_only_that_error(
    mock_site_context: Site,
) -> None:
    root = _post_upload(
        _RejectingUploadAction(), {"name": "Ada", "attachment": _upload()}
    )

    texts = _field_error_texts(root)
    assert "That file type is not allowed." in texts
    assert CHOOSE_AGAIN_MESSAGE not in texts


@pytest.mark.django_db
def test_a_422_with_no_file_chosen_has_no_choose_again_message(
    mock_site_context: Site,
) -> None:
    root = _post_upload(StubUploadFormAction(), {"name": ""})

    assert CHOOSE_AGAIN_MESSAGE not in _field_error_texts(root)


def test_a_form_invalid_override_still_gets_the_choose_again_message() -> None:
    request = RequestFactory().post("/", {"name": "", "attachment": _upload()})

    response = _OverridingInvalidAction().handle_submit(_ctx(request))

    assert response.status_code == 422
    assert response.content.decode() == CHOOSE_AGAIN_MESSAGE


class _RefreshingUploadAction(StubUploadFormAction):
    action_name = "refreshing_upload"
    refresh_on_change = ("name",)


def test_a_refresh_with_a_required_file_field_renders_the_form_bound() -> None:
    ctx = _ctx(RequestFactory().get("/", {"name": "Ada"}))

    form = _RefreshingUploadAction().get_form(ctx)

    assert form.is_bound
    assert not form.errors


def test_a_refresh_with_another_invalid_field_still_renders_unbound() -> None:
    ctx = _ctx(RequestFactory().get("/", {"name": ""}))

    form = _RefreshingUploadAction().get_form(ctx)

    assert not form.is_bound


class _OverridingSubmitAction(StubUploadFormAction):
    action_name = "overriding_submit"

    def handle_submit(self, ctx: PanelContext) -> HttpResponse:
        form = self.get_form(ctx)
        if form.is_valid():
            return self.form_valid(ctx, form)
        return self.form_invalid(ctx, form)


@pytest.mark.django_db
def test_a_handle_submit_override_still_gets_the_choose_again_message(
    mock_site_context: Site,
) -> None:
    root = _post_upload(
        _OverridingSubmitAction(), {"name": "", "attachment": _upload()}
    )

    assert _field_error_texts(root).count(CHOOSE_AGAIN_MESSAGE) == 1
    summary = " ".join(root.xpath("//*[@data-error-summary]//text()"))
    assert "2 fields to fix." in summary


@pytest.mark.django_db
def test_the_choose_again_message_is_added_once(mock_site_context: Site) -> None:
    root = _post_upload(StubUploadFormAction(), {"name": "", "attachment": _upload()})

    assert _field_error_texts(root).count(CHOOSE_AGAIN_MESSAGE) == 1


class _InlineUploadAction(StubUploadFormAction):
    action_name = "inline_upload"
    template_name = "panel_framework/test_inline_upload_form.html"
    renders_in_footer = False
    autofocus_first_field = False


class _InlineEditFileAction(EditAction):
    template_name = "panel_framework/test_inline_upload_form.html"
    renders_in_footer = False
    autofocus_first_field = False


def _inline_edit_file_action(item: StubFileModel) -> EditAction:
    return _InlineEditFileAction(
        form_class=_StubFileModelForm, form_title="Edit", instance=item
    )


def test_a_multipart_post_to_an_inline_form_action_reaches_form_valid_with_the_file() -> (
    None
):
    request = RequestFactory().post(
        "/", {"name": "Ada", "attachment": _upload(b"payload")}
    )
    _InlineUploadAction.received.clear()

    response = _InlineUploadAction().handle_submit(_ctx(request))

    assert response.content == b"saved"
    (form,) = _InlineUploadAction.received
    assert form.cleaned_data["attachment"].read() == b"payload"


@pytest.mark.django_db
def test_a_multipart_post_to_an_inline_edit_action_saves_the_file(
    mock_site_context: Site,
) -> None:
    item = make_stub_file(name="Record")
    request = RequestFactory().post(
        "/", {"name": "Record", "attachment": _upload(b"payload")}
    )
    request.user = make_staff_user()

    response = _inline_edit_file_action(item).handle_submit(_ctx(request, item))

    assert response.status_code == 204
    item.refresh_from_db()
    with item.attachment.open() as saved:
        assert saved.read() == b"payload"


@pytest.mark.django_db
def test_an_inline_form_get_posts_multipart(mock_site_context: Site) -> None:
    request = RequestFactory().get("/")
    request.user = make_staff_user()

    response = _InlineUploadAction().render_fragment(_ctx(request))

    (form,) = lxml.html.fromstring(response.content.decode()).xpath("//form")
    assert form.get("enctype") == "multipart/form-data"
    assert form.get("hx-encoding") == "multipart/form-data"


@pytest.mark.django_db
def test_an_inline_422_asks_for_the_file_again_in_the_files_described_by_line(
    mock_site_context: Site,
) -> None:
    root = _post_upload(_InlineUploadAction(), {"name": "", "attachment": _upload()})

    (file_input,) = root.xpath("//input[@name='attachment']")
    (line,) = root.xpath(f"//*[@id='{file_input.get('aria-describedby')}']")
    assert line.get("role") == "alert"
    assert CHOOSE_AGAIN_MESSAGE in line.text_content()


# -- EditableListAddAction tests -----------------------------------------


def _add_path(parent: StubModel) -> str:
    return f"stubs/{parent.pk}/__tabs/entries/__actions/add_entry"


def _entries_ctx(parent: StubModel, request: HttpRequest) -> PanelContext:
    return PanelContext(
        request=request,
        instance=parent,
        base_url=f"/stubs/{parent.pk}/__tabs/entries",
        name="entries",
        config=RecordingCapabilityConfig,
    )


class _OpenAddAction(EditableListAddAction):
    derive_capability = False
    capability = None


@pytest.mark.django_db
def test_a_valid_add_creates_the_entry_under_the_parent_and_answers_204(
    mock_site_context: Site,
) -> None:
    parent = make_stub()

    response = fetch(
        _add_path(parent),
        method="post",
        data={"title": "First", "detail": "note"},
        htmx=True,
    )

    entry = StubEntry.objects.get(title="First")
    assert response.status_code == 204
    assert entry.parent == parent
    assert response["HX-Trigger"] == build_hx_trigger(
        {"entryChanged": [str(entry.pk)]}, close_modal=True
    )


@pytest.mark.django_db
def test_an_invalid_add_answers_422_with_the_errors_and_the_typed_values(
    mock_site_context: Site,
) -> None:
    parent = make_stub()

    response = fetch(
        _add_path(parent),
        method="post",
        data={"title": "", "detail": "kept detail"},
        htmx=True,
    )

    content = response.content.decode()
    assert response.status_code == 422
    assert "This field is required." in content
    assert "kept detail" in content


@pytest.mark.django_db
def test_an_add_that_names_another_parent_saves_under_the_pages_parent(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    other = make_stub()

    fetch(
        _add_path(parent),
        method="post",
        data={"title": "Sneaky", "parent": str(other.pk)},
        htmx=True,
    )

    assert StubEntry.objects.get(title="Sneaky").parent == parent


@pytest.mark.django_db
def test_the_add_asks_the_add_capability_of_the_parent(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    panel = StubEditableListPanel(_entries_ctx(parent, request))

    EditableListAddAction(panel).has_permission(panel.ctx)

    assert RecordingCapabilityConfig.asked == [
        ("freedom_ls_panel_framework.add_stubentry", parent)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_denied_add_answers_403(mock_site_context: Site, method: str) -> None:
    parent = make_stub()
    RecordingCapabilityConfig.reset(answer=False)

    response = fetch(_add_path(parent), method=method, data={"title": "x"}, htmx=True)

    assert response.status_code == 403
    assert StubEntry.objects.count() == 0


@pytest.mark.django_db
def test_an_add_subclass_with_no_derived_capability_is_allowed_when_the_config_says_no(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    RecordingCapabilityConfig.reset(answer=False)
    request = RequestFactory().get("/")
    request.user = make_staff_user()
    panel = StubEditableListPanel(_entries_ctx(parent, request))

    assert _OpenAddAction(panel).has_permission(panel.ctx) is True


def _edit_path(parent: StubModel) -> str:
    return f"stubs/{parent.pk}/__tabs/entries/__actions/edit_entry"


def _hidden_entry_values(response: HttpResponse) -> list[str]:
    root = lxml.html.fromstring(f"<div>{response.content.decode()}</div>")
    return [
        str(value)
        for value in root.xpath("//form//input[@type='hidden'][@name='entry']/@value")
    ]


class _NameForm(forms.Form):
    name = forms.CharField()


class _PlainFormAction(FormPanelAction):
    label = "Rename"
    action_name = "rename"
    form_class = _NameForm


class _RowFormAction(_PlainFormAction):
    row_param = "item"

    def get_row_queryset(self, ctx: PanelContext) -> QuerySet[Model]:
        return cast(QuerySet[Model], StubModel.objects.all())


@pytest.mark.django_db
def test_a_row_scoped_edit_dialog_renders_its_entry_as_a_hidden_input_on_get(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha", "note")

    response = fetch(_edit_path(parent), data={"entry": str(entry.pk)}, htmx=True)

    assert response.status_code == 200
    assert _hidden_entry_values(response) == [str(entry.pk)]
    assert 'value="Alpha"' in response.content.decode()


@pytest.mark.django_db
def test_an_edit_post_saves_that_entry_and_fires_entry_changed_with_its_pk(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")

    response = fetch(
        _edit_path(parent),
        method="post",
        data={"entry": str(entry.pk), "title": "Renamed", "detail": "d"},
        htmx=True,
    )

    entry.refresh_from_db()
    assert response.status_code == 204
    assert entry.title == "Renamed"
    assert response["HX-Trigger"] == build_hx_trigger(
        {"entryChanged": [str(entry.pk)]}, close_modal=True
    )


@pytest.mark.django_db
def test_an_invalid_edit_answers_422_and_still_carries_the_hidden_entry(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")

    response = fetch(
        _edit_path(parent),
        method="post",
        data={"entry": str(entry.pk), "title": ""},
        htmx=True,
    )

    assert response.status_code == 422
    assert _hidden_entry_values(response) == [str(entry.pk)]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("which", ["another_parent", "missing", "malformed"])
def test_an_edit_for_an_entry_outside_the_parents_entries_is_a_404(
    mock_site_context: Site, method: str, which: str
) -> None:
    parent = make_stub()
    values = {
        "another_parent": str(make_stub_entry(make_stub(), "Theirs").pk),
        "missing": "999999",
        "malformed": "not-a-pk",
    }

    response = fetch(
        _edit_path(parent),
        method=method,
        data={"entry": values[which], "title": "x"},
        htmx=True,
    )

    assert response.status_code == 404


class _UnfilteredEntriesPanel(StubEditableListPanel):
    def get_entries(self) -> QuerySet[Model]:
        return cast(QuerySet[Model], StubEntry.objects.all())


@pytest.mark.django_db
def test_an_edit_narrows_to_the_parent_even_when_get_entries_forgets_the_filter(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    theirs = make_stub_entry(make_stub(), "Theirs")
    request = RequestFactory().get("/", {"entry": str(theirs.pk)})
    request.user = make_staff_user()
    panel = _UnfilteredEntriesPanel(_entries_ctx(parent, request))

    with pytest.raises(Http404):
        EditableListEditAction(panel).get_row_object(panel.ctx)


@pytest.mark.django_db
def test_an_edit_post_that_names_another_parent_leaves_the_entry_under_its_parent(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    other = make_stub()
    entry = make_stub_entry(parent, "Alpha")

    fetch(
        _edit_path(parent),
        method="post",
        data={"entry": str(entry.pk), "title": "Renamed", "parent": str(other.pk)},
        htmx=True,
    )

    entry.refresh_from_db()
    assert entry.parent == parent


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_denied_edit_answers_403(mock_site_context: Site, method: str) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")
    RecordingCapabilityConfig.reset(answer=False)

    response = fetch(
        _edit_path(parent),
        method=method,
        data={"entry": str(entry.pk), "title": "Renamed"},
        htmx=True,
    )

    entry.refresh_from_db()
    assert response.status_code == 403
    assert entry.title == "Alpha"


@pytest.mark.django_db
def test_a_form_action_with_a_row_param_renders_the_row_as_a_hidden_input(
    mock_site_context: Site,
) -> None:
    item = make_stub()
    action = _RowFormAction()
    request = RequestFactory().get("/", {"item": str(item.pk)})
    ctx = _ctx(request)

    root = lxml.html.fromstring(f"<div>{_render(action, ctx)}</div>")

    assert root.xpath("//form//input[@type='hidden'][@name='item']/@value") == [
        str(item.pk)
    ]


@pytest.mark.django_db
def test_a_form_action_without_a_row_param_renders_no_hidden_input(
    mock_site_context: Site,
) -> None:
    action = _PlainFormAction()
    ctx = _ctx(RequestFactory().get("/"))

    root = lxml.html.fromstring(f"<div>{_render(action, ctx)}</div>")

    assert root.xpath("//form//input[@type='hidden']") == []


def _remove_path(parent: StubModel) -> str:
    return f"stubs/{parent.pk}/__tabs/entries/__actions/remove_entry"


@pytest.mark.django_db
def test_a_remove_dialog_names_the_entry_and_says_it_cannot_be_undone(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")

    response = fetch(_remove_path(parent), data={"entry": str(entry.pk)}, htmx=True)

    html = response.content.decode()
    assert response.status_code == 200
    assert "Removing Alpha cannot be undone." in html
    assert _hidden_entry_values(response) == [str(entry.pk)]


@pytest.mark.django_db
def test_a_remove_post_deletes_the_entry_and_fires_entry_changed_with_its_pk(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")
    pk = entry.pk

    response = fetch(
        _remove_path(parent), method="post", data={"entry": str(pk)}, htmx=True
    )

    assert response.status_code == 204
    assert response["HX-Trigger"] == build_hx_trigger(
        {"entryChanged": [str(pk)]}, close_modal=True
    )
    assert not StubEntry.objects.filter(pk=pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("which", ["another_parent", "missing", "malformed"])
def test_a_remove_for_an_entry_outside_the_parents_entries_is_a_404(
    mock_site_context: Site, method: str, which: str
) -> None:
    parent = make_stub()
    values = {
        "another_parent": str(make_stub_entry(make_stub(), "Theirs").pk),
        "missing": "999999",
        "malformed": "not-a-pk",
    }

    response = fetch(
        _remove_path(parent),
        method=method,
        data={"entry": values[which]},
        htmx=True,
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_removing_a_protected_entry_answers_422_with_the_refusal_and_keeps_it(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")
    make_stub_entry_protected_child(entry)

    response = fetch(
        _remove_path(parent),
        method="post",
        data={"entry": str(entry.pk)},
        htmx=True,
    )

    assert response.status_code == 422
    assert (
        "This stub entry cannot be removed because it still has 1 stub entry "
        "protected child." in response.content.decode()
    )
    assert StubEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_denied_remove_answers_403(mock_site_context: Site, method: str) -> None:
    parent = make_stub()
    entry = make_stub_entry(parent, "Alpha")
    RecordingCapabilityConfig.reset(answer=False)

    response = fetch(
        _remove_path(parent),
        method=method,
        data={"entry": str(entry.pk)},
        htmx=True,
    )

    assert response.status_code == 403
    assert StubEntry.objects.filter(pk=entry.pk).exists()


CAP_LINE = "You can have up to 2. Remove one to add another."


def _capped_path(parent: StubModel, action_name: str) -> str:
    return f"stubs/{parent.pk}/__tabs/entries_capped/__actions/{action_name}"


def _full_capped_parent() -> tuple[StubModel, StubEntry]:
    parent = make_stub()
    make_stub_entry(parent, "Alpha")
    return parent, make_stub_entry(parent, "Beta")


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "post"])
def test_an_add_at_the_cap_answers_422_with_the_cap_line_and_creates_nothing(
    mock_site_context: Site, method: str
) -> None:
    parent, _ = _full_capped_parent()

    response = fetch(
        _capped_path(parent, "add_entry"),
        method=method,
        data={"title": "Third"},
        htmx=True,
    )

    assert response.status_code == 422
    assert CAP_LINE in response.content.decode()
    assert StubEntry.objects.filter(parent=parent).count() == 2


@pytest.mark.django_db
def test_an_edit_at_the_cap_still_saves(mock_site_context: Site) -> None:
    parent, entry = _full_capped_parent()

    response = fetch(
        _capped_path(parent, "edit_entry"),
        method="post",
        data={"entry": str(entry.pk), "title": "Renamed"},
        htmx=True,
    )

    entry.refresh_from_db()
    assert response.status_code == 204
    assert entry.title == "Renamed"


@pytest.mark.django_db
def test_a_remove_at_the_cap_still_deletes(mock_site_context: Site) -> None:
    parent, entry = _full_capped_parent()
    pk = entry.pk

    response = fetch(
        _capped_path(parent, "remove_entry"),
        method="post",
        data={"entry": str(pk)},
        htmx=True,
    )

    assert response.status_code == 204
    assert not StubEntry.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_an_add_through_a_panel_loaded_before_the_last_place_filled_is_refused(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    make_stub_entry(parent, "Alpha")
    request = RequestFactory().post("/", {"title": "Third"})
    request.user = make_staff_user()
    panel = StubCappedEditableListPanel(_entries_ctx(parent, request))
    assert len(panel.loaded_entries) == 1
    make_stub_entry(parent, "Beta")

    response = EditableListAddAction(panel).handle_submit(panel.ctx)

    assert response.status_code == 422
    assert StubEntry.objects.filter(parent=parent).count() == 2


def _add_another_path(parent: StubModel) -> str:
    return f"stubs/{parent.pk}/__tabs/entries_add_another/__actions/add_entry"


def _add_another_entries(parent: StubModel, count: int) -> None:
    for index in range(count):
        make_stub_entry(parent, f"Entry {index}")


@pytest.mark.django_db
def test_the_add_dialog_omits_add_and_add_another_when_the_panel_does_not_set_it(
    mock_site_context: Site,
) -> None:
    parent = make_stub()

    response = fetch(_add_path(parent), htmx=True)

    assert "Add and add another" not in response.content.decode()


@pytest.mark.django_db
def test_the_add_dialog_offers_add_and_add_another_before_add(
    mock_site_context: Site,
) -> None:
    parent = make_stub()

    html = fetch(_add_another_path(parent), htmx=True).content.decode()

    assert re.search(r"Add and add another.*?Adding….*?\bAdd\s*<", html, re.S)


@pytest.mark.django_db
def test_the_add_dialog_omits_add_and_add_another_on_the_last_free_place(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    _add_another_entries(parent, 2)

    response = fetch(_add_another_path(parent), htmx=True)

    assert "Add and add another" not in response.content.decode()


@pytest.mark.django_db
def test_add_and_add_another_keeps_the_dialog_open_on_an_empty_form(
    mock_site_context: Site,
) -> None:
    parent = make_stub()

    response = fetch(
        _add_another_path(parent),
        method="post",
        data={"title": "First", "action": "add_another"},
        htmx=True,
    )

    trigger = json.loads(response["HX-Trigger"])
    assert response.status_code == 200
    assert "Added First." in response.content.decode()
    assert trigger["entryChanged"]["ids"] == [
        str(StubEntry.objects.get(parent=parent).pk)
    ]
    assert "closeModal" not in trigger


@pytest.mark.django_db
def test_the_dialog_after_add_and_add_another_offers_only_add_on_the_last_free_place(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    _add_another_entries(parent, 1)

    response = fetch(
        _add_another_path(parent),
        method="post",
        data={"title": "Second", "action": "add_another"},
        htmx=True,
    )

    assert "Add and add another" not in response.content.decode()


@pytest.mark.django_db
def test_add_and_add_another_on_the_last_free_place_closes_the_dialog(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    _add_another_entries(parent, 2)

    response = fetch(
        _add_another_path(parent),
        method="post",
        data={"title": "Last", "action": "add_another"},
        htmx=True,
    )

    assert response.status_code == 204
    assert "closeModal" in json.loads(response["HX-Trigger"])


@pytest.mark.django_db
def test_add_and_add_another_on_the_last_free_place_saves_the_entry(
    mock_site_context: Site,
) -> None:
    parent = make_stub()
    _add_another_entries(parent, 2)

    fetch(
        _add_another_path(parent),
        method="post",
        data={"title": "Last", "action": "add_another"},
        htmx=True,
    )

    assert StubEntry.objects.filter(parent=parent, title="Last").exists()
