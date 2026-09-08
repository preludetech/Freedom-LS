"""CSV export shared by the referral-tracking admins."""

from __future__ import annotations

import codecs
import csv
from datetime import date

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse

FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_formula(value: str) -> str:
    """Stop a cell being executed as a formula when the CSV is opened."""
    if value and value[0] in FORMULA_TRIGGERS:
        return f"'{value}"
    return value


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, date):  # datetime is a date; both give ISO 8601
        return value.isoformat()
    return escape_csv_formula(str(value))


@admin.action(description="Export selected rows as CSV")
def export_as_csv(
    modeladmin: ModelAdmin, request: HttpRequest, queryset: QuerySet
) -> HttpResponse:
    fields = queryset.model._meta.fields
    relations = [f.name for f in fields if f.is_relation]
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="{queryset.model._meta.model_name}.csv"'
    )
    response.write(codecs.BOM_UTF8)
    writer = csv.writer(response)  # default QUOTE_MINIMAL
    writer.writerow([f.name for f in fields])
    for obj in queryset.select_related(*relations).iterator():
        writer.writerow([_cell(getattr(obj, f.name)) for f in fields])
    return response
