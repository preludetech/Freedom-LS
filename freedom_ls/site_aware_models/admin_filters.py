from datetime import datetime

from unfold.contrib.filters.admin import RangeDateTimeFilter
from unfold.utils import parse_datetime_str

from django.conf import settings
from django.contrib import admin
from django.core.validators import EMPTY_VALUES
from django.db.models import QuerySet
from django.forms import ValidationError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _


class CompletionListFilter(admin.SimpleListFilter):
    """Narrow a changelist to the rows that are complete, or the ones that aren't.

    Every progress model in FLS records completion as a nullable timestamp, so
    ``list_filter = ("complete_time",)`` falls through to ``DateFieldListFilter``
    -- which answers "when" ("today", "past 7 days") and never "whether". The
    whether is the question someone monitoring a cohort asks.

    Subclasses set ``completion_field`` to the timestamp's path on their model.
    """

    title = _("completion")
    parameter_name = "completion"
    completion_field: str

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        return [
            ("complete", gettext("Complete")),
            ("incomplete", gettext("Not complete")),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        value = self.value()
        if value not in {"complete", "incomplete"}:
            return queryset
        return queryset.filter(
            **{f"{self.completion_field}__isnull": value == "incomplete"}
        )


class InclusiveRangeDateTimeFilter(RangeDateTimeFilter):
    """A date range over a timestamp that works when only the dates are filled.

    Unfold's ``RangeDateTimeFilter`` renders a date box and a time box per bound
    and applies a bound only when *both* are filled. Someone narrowing a progress
    changelist to "the first week of September" fills the two date boxes, presses
    Apply Filters, and gets the whole list back with nothing on screen to say the
    range was dropped -- the failure is silent, and it reads as "the filter is
    broken" rather than "you missed a box".

    A blank time is not ambiguous, so this fills it in: the lower bound starts at
    the beginning of its day and the upper bound runs to the end of its day. That
    makes the range inclusive of both dates a person names, which is what naming
    two dates means. A time that *is* filled still wins, so narrowing to part of a
    day stays available.

    ``parse_datetime_str`` returns a naive datetime, which Django would warn about
    on a timezone-aware field, so each bound is made aware in the active timezone.
    """

    #: Times substituted per bound when the time box is left empty.
    BLANK_TIME_FROM = "00:00:00"
    BLANK_TIME_TO = "23:59:59.999999"

    def _bound(
        self, date_value: str | None, time_value: str | None, blank: str
    ) -> datetime | None:
        """One end of the range, or ``None`` when its date box is empty."""
        if date_value in EMPTY_VALUES:
            return None

        time_part = blank if time_value in EMPTY_VALUES else time_value
        parsed: datetime | None = parse_datetime_str(f"{date_value} {time_part}")
        if parsed is None:
            return None

        if settings.USE_TZ and timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet | None:
        filters = {}

        lower = self._bound(
            self.used_parameters.get(f"{self.parameter_name}_from_0"),
            self.used_parameters.get(f"{self.parameter_name}_from_1"),
            self.BLANK_TIME_FROM,
        )
        if lower is not None:
            filters[f"{self.parameter_name}__gte"] = lower

        upper = self._bound(
            self.used_parameters.get(f"{self.parameter_name}_to_0"),
            self.used_parameters.get(f"{self.parameter_name}_to_1"),
            self.BLANK_TIME_TO,
        )
        if upper is not None:
            filters[f"{self.parameter_name}__lte"] = upper

        try:
            return queryset.filter(**filters)
        except (ValueError, ValidationError):
            return None
