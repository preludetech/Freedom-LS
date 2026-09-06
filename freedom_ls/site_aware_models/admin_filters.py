from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
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
