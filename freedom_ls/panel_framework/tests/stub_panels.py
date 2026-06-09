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

from typing import cast

from django import forms
from django.apps import apps
from django.db.models import Model, QuerySet
from django.http import HttpRequest, QueryDict
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from freedom_ls.panel_framework.actions import CreateInstanceAction, PanelAction
from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.views import InstanceView, ListViewConfig


def _stub_model() -> type[Model]:
    return apps.get_model("freedom_ls_panel_framework", "stubmodel")


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

    def has_permission(
        self, request: HttpRequest, instance: Model | None = None
    ) -> bool:
        # Stub: always allow in tests so the create button appears in e2e tests
        # without needing login. Permission enforcement is tested separately in
        # test_panel_actions.py using its own StubCreateAction.
        return True

    def get_success_url(self, instance: Model) -> str:
        return f"/items/{instance.pk}"

    def get_created_event_name(self) -> str:
        return "itemCreated"


class StubDataTable(DataTable):
    @staticmethod
    def get_queryset(request: HttpRequest) -> QuerySet:
        return cast(QuerySet, _stub_model().objects.all())

    @staticmethod
    def get_columns() -> list[dict[str, object]]:
        return [
            {
                "header": "Name",
                "template": "cotton/data-table-cells/text.html",
                "attr": "name",
                "sortable": True,
            },
        ]


class StubDataTablePanel(DataTablePanel):
    title = "Stub"
    data_table = StubDataTable


class StubInstanceView(InstanceView):
    panels = {
        "default": StubDataTablePanel,
    }


class StubListConfig(ListViewConfig):
    url_name = "stubs"
    menu_label = "Stubs"
    list_view = StubDataTable
    instance_view = StubInstanceView

    @classmethod
    def get_actions(cls, request: HttpRequest) -> list[PanelAction]:
        return [StubCreateAction()]

    @classmethod
    def get_instance_view(cls, pk: str) -> InstanceView:
        instance: Model = get_object_or_404(_stub_model(), pk=pk)
        assert cls.instance_view is not None
        return cls.instance_view(instance)
