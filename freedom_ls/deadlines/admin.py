from __future__ import annotations

from datetime import datetime
from typing import cast

from unfold.admin import ModelAdmin, TabularInline

from django import forms
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import BaseInlineFormSet
from django.http import HttpRequest
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.deadlines.models import (
    CohortDeadlineOverride,
    DeadlineKind,
    LearnerDeadlineOverride,
    course_viewable_collection_items,
)
from freedom_ls.deadlines.queries import (
    canonical_beneath,
    content_default_for,
    layers_beneath,
)
from freedom_ls.deadlines.resolver import (
    DeadlineLayer,
    DeadlineSource,
    DeadlineValue,
    ResolvedDeadline,
    course_deadlines,
    due_instant,
)
from freedom_ls.learner_management.admin import CohortCourseRegistrationAdmin
from freedom_ls.learner_progress.admin import CourseProgressAdmin
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.time_zones import site_time_zone

DeadlineOverride = CohortDeadlineOverride | LearnerDeadlineOverride


class CollectionItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: ContentCollectionItem) -> str:
        child = obj.child
        if child is None:
            return str(obj.pk)
        return f"{child.title} ({child.file_path})"


class DeadlineOverrideFormSet(BaseInlineFormSet):
    """Stamps who saved a row and what it replaced. The parent admin belongs to another app,
    so the stamping lives on the formset the inline hands it rather than in save_formset."""

    set_by: User

    def save_new(self, form: forms.ModelForm, commit: bool = True) -> DeadlineOverride:
        instance = cast(DeadlineOverride, super().save_new(form, commit=False))
        return self._stamped(instance, commit)

    def save_existing(
        self,
        form: forms.ModelForm,
        obj: DeadlineOverride,
        commit: bool = True,
    ) -> DeadlineOverride:
        instance = cast(
            DeadlineOverride, super().save_existing(form, obj, commit=False)
        )
        return self._stamped(instance, commit)

    def _stamped(self, instance: DeadlineOverride, commit: bool) -> DeadlineOverride:
        instance.set_by = self.set_by
        instance.replaced_value = canonical_beneath(instance)
        if commit:
            instance.save()
        return instance


def site_zone_text(instant: datetime) -> str:
    """An instant as the admin shows it: the site zone, named."""
    return f"{instant:%-d %b %Y, %H:%M} {instant.tzname()}"


def _value_text(value: DeadlineValue | None, obj: DeadlineOverride) -> str:
    """A value as the admin shows it: a fixed date in the site zone, a relative one as its
    offset, since no learner's registration date applies to a cohort-wide row."""
    if value is None:
        return "None"
    if value.kind == DeadlineKind.NONE:
        return "No deadline"
    at = f" at {value.due_time:%H:%M}" if value.due_time is not None else ""
    if value.kind == DeadlineKind.FIXED and value.due_date is not None:
        instant = due_instant(value, value.due_date, site_time_zone(obj.site))
        return f"Fixed {site_zone_text(instant)}" if instant is not None else "None"
    return f"{value.due_days_after_registration} days after registration{at}"


class DeadlineOverrideInline(TabularInline):
    """Shared shape of the override inlines; the subclass names the model. Both parent
    models carry a course, so the parent's course needs no subclass hook."""

    extra = 0
    formset = DeadlineOverrideFormSet
    fields = [
        "collection_item",
        "kind",
        "due_date",
        "due_time",
        "due_days_after_registration",
        "reason",
        "content_default",
        "effective_value",
        "default_changed_note",
        "set_by",
    ]
    readonly_fields = [
        "content_default",
        "effective_value",
        "default_changed_note",
        "set_by",
    ]
    verbose_name = "deadline override"

    def parent_course(self, request: HttpRequest) -> Course | None:
        """The course of the object being edited, or None on the add page or for a malformed id.
        Read through the site-aware manager, so another site's parent is never reached."""
        object_id = (
            request.resolver_match.kwargs.get("object_id")
            if request.resolver_match
            else None
        )
        if object_id is None:
            return None
        try:
            parent = (
                self.parent_model.objects.select_related("course")
                .filter(pk=unquote(object_id))
                .first()
            )
        except (ValidationError, ValueError):
            return None
        return parent.course if parent is not None else None

    def get_formset(
        self, request: HttpRequest, obj: object | None = None, **kwargs: object
    ) -> type[BaseInlineFormSet]:
        formset = cast(
            type[DeadlineOverrideFormSet], super().get_formset(request, obj, **kwargs)
        )
        formset.set_by = cast(User, request.user)
        return formset

    def formfield_for_foreignkey(
        self,
        db_field: models.ForeignKey,
        request: HttpRequest,
        **kwargs: object,
    ) -> forms.ModelChoiceField | None:
        # The picker offers only the parent course's own rows. On the add page there is no
        # course yet, so it offers nothing; clean() refuses a row from another course regardless.
        if db_field.name == "collection_item":
            course = self.parent_course(request)
            kwargs["form_class"] = CollectionItemChoiceField
            kwargs["queryset"] = (
                ContentCollectionItem.objects.filter(
                    pk__in=[i.pk for i in course_viewable_collection_items(course)]
                )
                if course is not None
                else ContentCollectionItem.objects.none()
            )
        field = cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(db_field, request, **kwargs),
        )
        if field is not None and db_field.name == "collection_item":
            # Set after the call: unfold replaces the empty label with its own.
            field.empty_label = "Course time limit"
        return field

    @admin.display(description="Content default")
    def content_default(self, obj: DeadlineOverride) -> str:
        if not obj.pk:
            return ""
        return _value_text(content_default_for(obj), obj)

    @admin.display(description="Effective")
    def effective_value(self, obj: DeadlineOverride) -> str:
        if not obj.pk:
            return ""
        layers = [
            DeadlineLayer(
                DeadlineSource.COHORT_REGISTRATION, obj.value(), obj.replaced_value
            ),
            *layers_beneath(obj),
        ]
        winner = next(
            (layer.value for layer in layers if layer.value is not None), None
        )
        return _value_text(winner, obj)

    @admin.display(description="Default changed")
    def default_changed_note(self, obj: DeadlineOverride) -> str:
        if not obj.pk:
            return ""
        beneath = canonical_beneath(obj)
        if obj.replaced_value == beneath:
            return ""
        return (
            "Default has changed since this override was set "
            f"(was {obj.replaced_value or 'nothing'}, now {beneath or 'nothing'})"
        )


SOURCE_LABELS: dict[DeadlineSource, str] = {
    DeadlineSource.CONTENT: "Content default",
    DeadlineSource.COHORT_REGISTRATION: "Cohort override",
    DeadlineSource.LEARNER: "Learner override",
}


class CohortDeadlineOverrideInline(DeadlineOverrideInline):
    model = CohortDeadlineOverride


class LearnerDeadlineOverrideInline(DeadlineOverrideInline):
    model = LearnerDeadlineOverride


def _deadline_line(label: str, resolved: ResolvedDeadline) -> tuple[str, str, str]:
    source = SOURCE_LABELS[resolved.source] if resolved.source is not None else ""
    return (label, site_zone_text(resolved.due_at) if resolved.due_at else "", source)


@admin.display(description="Effective deadlines")
def effective_deadlines(model_admin: ModelAdmin, record: CourseProgress) -> SafeString:
    """Every collection item with a deadline, its due instant in the site zone and its source,
    then the time limit end; one line each, built from the same resolver the learner sees.
    Titles are author text, so every line goes through format_html."""
    if record._state.adding:
        return format_html("{}", "")
    deadlines = course_deadlines(record)
    lines: list[tuple[str, str, str]] = []
    for item in course_viewable_collection_items(record.course):
        resolved = deadlines.items.get(item.pk)
        if resolved is None or resolved.due_at is None:
            continue
        title = item.child.title if item.child is not None else str(item.pk)
        lines.append(_deadline_line(title, resolved))
    if deadlines.time_limit.due_at is not None:
        lines.append(_deadline_line("Course time limit end", deadlines.time_limit))
    if not lines:
        return format_html("<p>{}</p>", "No deadlines.")
    return format_html(
        "<ul>{}</ul>",
        format_html_join("", "<li>{}: {} ({})</li>", lines),
    )


# This change page belongs to an app below this one in docs/app_structure.md, so the override
# inline is added from here rather than imported there. The seam adds rather than replaces.
CohortCourseRegistrationAdmin.inlines = [
    *CohortCourseRegistrationAdmin.inlines,
    CohortDeadlineOverrideInline,
]


# CourseProgressAdmin's change page likewise belongs to a lower app; the inline, the read-only
# field and its fieldset are added from here. Each seam adds rather than replaces.
CourseProgressAdmin.inlines = [
    *CourseProgressAdmin.inlines,
    LearnerDeadlineOverrideInline,
]
setattr(CourseProgressAdmin, "effective_deadlines", effective_deadlines)  # noqa: B010
setattr(  # noqa: B010
    CourseProgressAdmin,
    "readonly_fields",
    (*CourseProgressAdmin.readonly_fields, "effective_deadlines"),
)
setattr(  # noqa: B010
    CourseProgressAdmin,
    "fieldsets",
    (
        *CourseProgressAdmin.fieldsets,
        ("Deadlines", {"fields": ("effective_deadlines",)}),
    ),
)
