from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _


class ContentTagListFilter(admin.SimpleListFilter):
    """Narrow a content changelist to one tag from its ``tags`` ArrayField.

    Django has no field list filter for ``ArrayField``, so a plain
    ``list_filter = ("tags",)`` falls through to ``AllValuesFieldListFilter``,
    which offers whole stored arrays as choices and hands them back as strings
    the database cannot parse as an array literal.
    """

    title = _("tags")
    parameter_name = "tag"

    def lookups(
        self, request: HttpRequest, model_admin: admin.ModelAdmin
    ) -> list[tuple[str, str]]:
        # Distinct arrays, flattened in Python. Unnesting in the database would
        # mean raw SQL, and the content tables this filter serves are small.
        stored = model_admin.get_queryset(request).values_list("tags", flat=True)
        return sorted((tag, tag) for tag in {tag for tags in stored for tag in tags})

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        tag = self.value()
        if tag is None:
            return queryset
        return queryset.filter(tags__contains=[tag])
