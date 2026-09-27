"""Shared stub Panel/DataTable/InstanceView definitions for panel_framework tests.

These exist only so panel_framework tests can exercise the framework without
depending on any consumer app. They are imported by both pytest modules and
the Django URL config under ``tests/urls.py``.

Note on lazy ``StubModel`` lookup
---------------------------------
``StubModel`` is defined in ``conftest.py`` and pytest auto-discovers that
file. In this project's namespace-package layout (no ``freedom_ls/__init__.py``)
pytest loads conftest under one module path while Django's URL resolver
loads ``urls.py`` (and therefore this module) under another. A direct
``from .conftest import StubModel`` here would create a second copy of the
class and Django's app registry rejects the duplicate. We dodge that by
fetching the model through the registry at call time, after conftest has
registered it under the ``freedom_ls_panel_framework`` app label.
"""

from __future__ import annotations

from typing import ClassVar, cast

from django import forms
from django.apps import apps
from django.db.models import Field, Model, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from freedom_ls.panel_framework.actions import CreateInstanceAction, PanelAction
from freedom_ls.panel_framework.context import PanelContext
from freedom_ls.panel_framework.filters import (
    BooleanFilter,
    ChoiceFilter,
    RelatedChoiceFilter,
    TableFilter,
)
from freedom_ls.panel_framework.panels import (
    DataTablePanel,
    Panel,
    PanelStack,
    TabSet,
)
from freedom_ls.panel_framework.tables import Column, DataTable
from freedom_ls.panel_framework.views import (
    BaseViewConfig,
    InstanceView,
    ListViewConfig,
    NavGroup,
    SectionConfigBase,
)


class RecordingCapabilityConfig(SectionConfigBase):
    """A `has_capability` that records every (capability, scope) it is asked
    and answers a class-level canned decision, so a permission test can
    assert on both without a real role config behind it.

    ``reset()`` clears the recording and sets the answer and scope for one
    test; the autouse fixture in conftest.py calls it between every test so
    none of this state leaks across the suite.
    """

    answer: ClassVar[bool] = True
    scope: ClassVar[Model | None] = None
    asked: ClassVar[list[tuple[str, Model]]] = []

    @classmethod
    def reset(cls, *, answer: bool = True, scope: Model | None = None) -> None:
        cls.answer = answer
        cls.scope = scope
        cls.asked = []

    @classmethod
    def get_scope(cls, request: HttpRequest) -> Model | None:
        return cls.scope

    @classmethod
    def has_capability(
        cls, request: HttpRequest, capability: str, scope: Model
    ) -> bool:
        cls.asked.append((capability, scope))
        return cls.answer


def _stub_model() -> type[Model]:
    return apps.get_model("freedom_ls_panel_framework", "stubmodel")


def _stub_child_model() -> type[Model]:
    return apps.get_model("freedom_ls_panel_framework", "stubchild")


def _build_stub_create_form(
    data: QueryDict | None = None, instance: Model | None = None
) -> forms.ModelForm:
    """Build a ModelForm instance for StubModel, resolved lazily via the app registry."""
    StubModelCls = _stub_model()

    class _StubModelForm(forms.ModelForm):
        class Meta:
            model = StubModelCls
            fields = ["name"]

    return _StubModelForm(data, instance=instance)


class StubCreateAction(CreateInstanceAction):
    form_title = "Create Item"
    label = "Create Item"
    action_name = "create_item"
    # form_class must be set but is not used directly — get_form and
    # has_permission are overridden below to use the lazy _build_stub_create_form
    # helper, since StubModel cannot be imported at module level (see module docstring).
    form_class = forms.ModelForm  # placeholder; not used directly

    def get_form(
        self, request: HttpRequest, instance: Model | None = None
    ) -> forms.ModelForm:
        data = request.POST if request.method == "POST" else None
        return _build_stub_create_form(data=data, instance=instance)

    def _render_empty_form(self, request: HttpRequest, form_url: str) -> str:
        """Re-render the modal form with a fresh, empty form for StubModel."""
        form = _build_stub_create_form()
        return render_to_string(
            "panel_framework/partials/modal_form.html",
            {
                "form": form,
                "form_title": self.form_title,
                "form_url": form_url,
                "variant": self.variant,
                "label": self.label,
                "submit_buttons": self.submit_buttons,
                "modal_open": "True",
            },
            request=request,
        )

    def has_permission(self, ctx: PanelContext) -> bool:
        # Stub: always allow in tests so the create button appears in playwright tests
        # without needing login. Permission enforcement is tested separately in
        # test_panel_actions.py using its own StubCreateAction.
        return True

    def get_success_url(self, instance: Model) -> str:
        return f"/items/{instance.pk}"

    def get_created_event_name(self) -> str:
        return "itemCreated"


class StubDataTable(DataTable):
    search_fields = ["name"]

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return cast(QuerySet, _stub_model().objects.order_by("name"))

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Name",
                template="cotton/data-table-cells/text.html",
                attr="name",
                sortable=True,
            ),
        ]

    @staticmethod
    def get_filters() -> list[TableFilter]:
        kind_field = cast(Field, _stub_model()._meta.get_field("kind"))
        kind_choices = list(kind_field.choices or [])
        return [
            ChoiceFilter(
                "kind", "Kind", lookup="kind", choices=kind_choices, always_shown=True
            ),
            BooleanFilter("active", "Active only", lookup="is_active"),
        ]


class StubDataTablePanel(DataTablePanel):
    title = "Stub"
    data_table = StubDataTable
    table_key = "stub"


class StubChildDataTable(DataTable):
    """A table over StubChild, whose one filter narrows by its parent —
    the RelatedChoiceFilter case, scoped to a subset of StubModel rows."""

    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return cast(
            QuerySet,
            _stub_child_model().objects.select_related("parent").order_by("pk"),
        )

    @staticmethod
    def get_columns() -> list[Column]:
        return [
            Column(
                header="Parent",
                template="cotton/data-table-cells/text.html",
                attr="parent",
            ),
        ]

    @staticmethod
    def get_filters() -> list[TableFilter]:
        return [
            RelatedChoiceFilter(
                "parent",
                "Parent",
                lookup="parent",
                queryset=_stub_model().objects.filter(name__startswith="in-scope"),
            ),
        ]


class StubChildTablePanel(DataTablePanel):
    title = "Children"
    data_table = StubChildDataTable
    table_key = "children"


class StubATablePanel(DataTablePanel):
    title = "A"
    data_table = StubDataTable
    table_key = "a"


class StubBTablePanel(DataTablePanel):
    title = "B"
    data_table = StubDataTable
    table_key = "b"


class StubPairStack(PanelStack):
    title = "Pair"
    children = {"a": StubATablePanel, "b": StubBTablePanel}


class StubDetailsPanel(Panel):
    """A leaf that prints its instance's name through a template of its own."""

    title = "Details"
    template_name = "panel_framework/test_stub_details.html"


class StubHiddenPanel(Panel):
    title = "Hidden"

    def has_permission(self, request: HttpRequest) -> bool:
        return False


class StubTabSet(TabSet):
    title = "Stub sections"
    children = {
        "default": StubDataTablePanel,
        "details": StubDetailsPanel,
        "hidden": StubHiddenPanel,
        "pair": StubPairStack,
        "children": StubChildTablePanel,
    }


class StubInstanceView(InstanceView):
    panel = StubTabSet


class StubListConfig(RecordingCapabilityConfig, ListViewConfig):
    url_name = "stubs"
    menu_label = "Stubs"
    list_view = StubDataTable
    table_key = "stubs"
    instance_view = StubInstanceView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [StubCreateAction()]

    @classmethod
    def get_instance_view(cls, request: HttpRequest, pk: str) -> InstanceView:
        instance: Model = get_object_or_404(_stub_model(), pk=pk)
        assert cls.instance_view is not None
        return cls.instance_view(instance)


class StubBaseConfig(RecordingCapabilityConfig, BaseViewConfig):
    """A base view holding an instance-free table panel."""

    url_name = "stub-base"
    menu_label = "Stub base"
    panel = StubDataTablePanel


STUB_CONFIG = [NavGroup("Stubs", [StubListConfig, StubBaseConfig])]
