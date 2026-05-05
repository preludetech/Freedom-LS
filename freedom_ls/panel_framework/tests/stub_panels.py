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

from django.apps import apps
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from freedom_ls.panel_framework.panels import DataTablePanel
from freedom_ls.panel_framework.tables import DataTable
from freedom_ls.panel_framework.views import InstanceView, ListViewConfig


def _stub_model() -> type[Model]:
    return apps.get_model("freedom_ls_panel_framework", "stubmodel")


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
    def get_instance_view(cls, pk: str) -> InstanceView:
        instance: Model = get_object_or_404(_stub_model(), pk=pk)
        assert cls.instance_view is not None
        return cls.instance_view(instance)
