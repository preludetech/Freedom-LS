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

from freedom_ls.panel_framework.actions import (
    CreateInstanceAction,
    DeleteAction,
    PanelAction,
)
from freedom_ls.panel_framework.bulk_actions import BulkAction
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
from freedom_ls.panel_framework.quick_view import QuickView
from freedom_ls.panel_framework.tables import Column, DataTable, ExportColumn
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
    success_events = ("itemChanged",)
    # Wrapped in staticmethod so `self.form_class` returns the plain function
    # unbound: assigned bare, Python's function descriptor would bind it to
    # the action instance and inject self as its first positional argument.
    # has_permission is still overridden below: the base implementation reads
    # form_class.Meta.model, which only a ModelForm subclass has.
    form_class = staticmethod(_build_stub_create_form)

    def has_permission(self, ctx: PanelContext) -> bool:
        # Stub: always allow in tests so the create button appears in playwright tests
        # without needing login. Permission enforcement is tested separately in
        # test_panel_actions.py using its own StubCreateAction.
        return True

    def get_success_url(self, instance: Model) -> str:
        # A real, reachable page under this app's own test URLconf, so a
        # browser test can follow the HX-Location this action's "Save"
        # sends and see actual content, not a 404.
        return f"/test-panel/framework/stubs/{instance.pk}"


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
                template="cotton/data-table-cells/link.html",
                text_attr="name",
                url_name="panel_framework_test:framework",
                url_path_template="stubs/{pk}",
                quick_view=True,
                sortable=True,
                card="primary",
            ),
            Column(
                header="Kind",
                template="cotton/data-table-cells/text.html",
                attr="get_kind_display",
                card="secondary",
            ),
            Column(
                header="SAT score",
                template="cotton/data-table-cells/text.html",
                attr="sat_score",
                card="md_only",
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

    @staticmethod
    def get_export_columns() -> list[ExportColumn]:
        return [
            ExportColumn("Name", "name"),
            ExportColumn("Kind", lambda row: row.get_kind_display()),
        ]


class StubBulkAction(BulkAction):
    label = "Mark processed"
    action_name = "stub_bulk"

    def execute(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_active=False)


class StubForbiddenBulkAction(BulkAction):
    label = "Forbidden bulk action"
    action_name = "stub_forbidden_bulk"

    def has_permission(self, request: HttpRequest) -> bool:
        return False


class StubDataTablePanel(DataTablePanel):
    title = "Stub"
    data_table = StubDataTable
    table_key = "stub"
    refresh_events = ("itemChanged",)

    def get_bulk_actions(self) -> list[BulkAction]:
        return [StubBulkAction(), StubForbiddenBulkAction()]


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


class StubPlainDataTable(DataTable):
    """The same rows as StubDataTable, with no filters and no sortable
    columns — table b's role in the mobile toolbar tests, where the Filter
    and Sort buttons must not render."""

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
                card="primary",
            ),
        ]


class StubBTablePanel(DataTablePanel):
    title = "B"
    data_table = StubPlainDataTable
    table_key = "b"


class StubPairStack(PanelStack):
    title = "Pair"
    children = {"a": StubATablePanel, "b": StubBTablePanel}


class StubCardDataTable(StubDataTable):
    """The same rows and columns as StubDataTable, with its default card
    body replaced by a custom template."""

    card_template = "panel_framework/test_stub_card.html"


class StubCardTablePanel(DataTablePanel):
    title = "Cards"
    data_table = StubCardDataTable
    table_key = "cards"


class StubDeleteAction(DeleteAction):
    def has_permission(self, ctx: PanelContext) -> bool:
        # Stub: always allow in tests, the way StubCreateAction does.
        return True


class StubReadOnlyAction(PanelAction):
    """A test-only read-only modal fragment: a heading with no form, proving
    that a PanelAction needs neither a form nor a delete confirmation to open
    the shared modal."""

    label = "View Info"
    action_name = "view_info"
    trigger_template_name = "panel_framework/partials/modal_trigger.html"
    template_name = "panel_framework/test_read_only_fragment.html"


class StubDetailsPanel(Panel):
    """A leaf that prints its instance's name through a template of its own."""

    title = "Details"
    template_name = "panel_framework/test_stub_details.html"

    def get_actions(self) -> list[PanelAction]:
        return [
            StubDeleteAction(success_url="/test-panel/framework/stubs"),
            StubReadOnlyAction(),
        ]


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
        "cards": StubCardTablePanel,
    }


class StubInstanceView(InstanceView):
    panel = StubTabSet


class StubQuickView(QuickView):
    template_name = "panel_framework/test_stub_quick_view.html"
    refresh_events = ("itemChanged",)


class StubListConfig(RecordingCapabilityConfig, ListViewConfig):
    url_name = "stubs"
    menu_label = "Stubs"
    list_view = StubDataTable
    table_key = "stubs"
    instance_view = StubInstanceView
    refresh_events = ("itemChanged",)
    quick_view = StubQuickView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [StubCreateAction()]

    @classmethod
    def get_bulk_actions(cls, request: HttpRequest) -> list[BulkAction]:
        return [StubBulkAction()]

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
