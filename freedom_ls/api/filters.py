from __future__ import annotations

import re
from datetime import date, datetime

import django_filters
from django_filters.fields import IsoDateTimeField
from django_filters.filters import IsoDateTimeFilter

from django import forms
from django.utils import timezone
from django.utils.dateparse import parse_datetime


class AwareIsoDateTimeField(IsoDateTimeField):
    def to_python(self, value: str | None) -> datetime | None:
        # Django's DateTimeField parses the value itself and localises a naive
        # result before strptime is consulted, so the rejection has to happen here.
        if value not in self.empty_values:
            try:
                parsed = parse_datetime(str(value).strip())
            except ValueError as exc:
                raise forms.ValidationError(
                    self.error_messages["invalid"], code="invalid"
                ) from exc
            if parsed is not None and timezone.is_naive(parsed):
                raise forms.ValidationError(
                    "Give the time with a timezone offset or Z.", code="naive"
                )
        result: datetime | None = super().to_python(value)
        return result


class AwareIsoDateTimeFilter(IsoDateTimeFilter):
    field_class = AwareIsoDateTimeField


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class IsoDateField(forms.DateField):
    # One format, so a datetime or a localised date is rejected rather than parsed.
    input_formats = ["%Y-%m-%d"]
    default_error_messages = {"invalid": "Give a date as YYYY-MM-DD."}

    def to_python(self, value: str | datetime | date | None) -> date | None:
        # strptime's %m and %d also take a single digit, so the padding is
        # checked here before the format is consulted.
        if (
            isinstance(value, str)
            and value.strip()
            and not _ISO_DATE.match(value.strip())
        ):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")
        result: date | None = super().to_python(value)
        return result


class IsoDateFilter(django_filters.DateFilter):
    field_class = IsoDateField


class UpdatedSinceFilterSet(django_filters.FilterSet):
    updated_since = AwareIsoDateTimeFilter(field_name="updated_at", lookup_expr="gte")
