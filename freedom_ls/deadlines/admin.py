from __future__ import annotations

from datetime import timedelta
from typing import cast
from uuid import UUID

from unfold.admin import ModelAdmin, TabularInline

from django import forms
from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models import BaseConstraint, Model
from django.forms import BaseInlineFormSet
from django.forms.formsets import DELETION_FIELD_NAME
from django.http import HttpRequest
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from freedom_ls.accounts.models import User
from freedom_ls.content_engine.models import ContentCollectionItem, Course
from freedom_ls.deadlines.loader import get_deadline_policy
from freedom_ls.deadlines.models import (
    CONFIG_FIELDS,
    SWITCH_FIELDS,
    CohortCourseRegistrationDeadlineConfig,
    CohortDeadlineConfig,
    CohortDeadlineOverride,
    CourseDeadlineConfig,
    DeadlineKind,
    LearnerCourseRegistrationDeadlineConfig,
    LearnerDeadlineOverride,
    OrganisationDeadlineConfig,
    SiteDeadlineConfig,
)
from freedom_ls.deadlines.queries import canonical_beneath, content_default_for
from freedom_ls.deadlines.resolver import (
    DeadlineSource,
    DeadlineValue,
    LayerRows,
    ResolvedDeadline,
    course_deadlines,
    due_instant,
)
from freedom_ls.learner_management.admin import CohortCourseRegistrationAdmin
from freedom_ls.learner_progress.admin import CourseProgressAdmin
from freedom_ls.learner_progress.models import CourseProgress
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from freedom_ls.site_aware_models.forms import ConstraintValidationFormMixin
from freedom_ls.site_aware_models.time_zones import site_time_zone, site_zone_text

DeadlineOverride = CohortDeadlineOverride | LearnerDeadlineOverride

VALUE_FIELDS = frozenset(
    {"collection_item", "kind", "due_date", "due_time", "due_days_after_registration"}
)
TIME_LIMIT_DUPLICATE = "The course time limit already has an override here."
ITEM_DUPLICATE = "This item already has an override here."


def duplicate_error(collection_item_id: UUID | None) -> ValidationError:
    """The clash for one target, worded for an admin rather than as a constraint name."""
    if collection_item_id is None:
        return ValidationError(TIME_LIMIT_DUPLICATE, code="unique")
    return ValidationError(ITEM_DUPLICATE, code="unique")


class CollectionItemChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: ContentCollectionItem) -> str:
        child = obj.child
        if child is None:
            return str(obj.pk)
        return f"{child.title} ({child.file_path})"


class DeadlineOverrideForm(ConstraintValidationFormMixin):
    """Checks the one-override-per-target constraints while cleaning and words a clash for
    an admin, not as a constraint name. The clash belongs to the row, not to one field."""

    def _error_key(self, constraint: BaseConstraint) -> str:
        return NON_FIELD_ERRORS

    def _reworded(
        self,
        model_class: type[Model],
        constraint: BaseConstraint,
        error: ValidationError,
    ) -> ValidationError:
        return duplicate_error(self.instance.collection_item_id)


class DeadlineOverrideFormSet(BaseInlineFormSet):
    """Stamps who saved a row and what it replaced. The parent admin belongs to another app,
    so the stamping lives on the formset the inline hands it rather than in save_formset."""

    set_by: User

    def clean(self) -> None:
        # Both unique constraints are conditional, which Django's formset uniqueness check
        # skips, and the form-level check only sees saved rows. Two rows for one target in
        # the same submit would otherwise reach the database.
        super().clean()
        seen: set[UUID | None] = set()
        for form in self.forms:
            if not form.is_valid() or form.cleaned_data.get(DELETION_FIELD_NAME):
                continue
            target = form.cleaned_data.get("collection_item")
            target_id = target.pk if target is not None else None
            if target_id in seen:
                raise duplicate_error(target_id)
            seen.add(target_id)

    def save_new(self, form: forms.ModelForm, commit: bool = True) -> DeadlineOverride:
        instance = cast(DeadlineOverride, super().save_new(form, commit=False))
        return self._stamped(instance, commit, restamp=True)

    def save_existing(
        self,
        form: forms.ModelForm,
        obj: DeadlineOverride,
        commit: bool = True,
    ) -> DeadlineOverride:
        instance = cast(
            DeadlineOverride, super().save_existing(form, obj, commit=False)
        )
        # What the row replaced is read again only when the row's value moved; editing
        # the reason alone must not clear a "Default has changed" note.
        restamp = not VALUE_FIELDS.isdisjoint(form.changed_data)
        return self._stamped(instance, commit, restamp=restamp)

    def _stamped(
        self, instance: DeadlineOverride, commit: bool, *, restamp: bool
    ) -> DeadlineOverride:
        instance.set_by = self.set_by
        if restamp:
            instance.replaced_value = canonical_beneath(instance)
        if commit:
            instance.save()
        return instance


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
    days = value.due_days_after_registration
    return f"{days} day{'' if days == 1 else 's'} after registration{at}"


class DeadlineOverrideInline(TabularInline):
    """Shared shape of the override inlines; the subclass names the model. Both parent
    models carry a course, so the parent's course needs no subclass hook."""

    extra = 0
    form = DeadlineOverrideForm
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
    # The path from a row to its course, which the read-only columns read for every row.
    parent_select_related: tuple[str, ...] = ()
    # The cohort rows beneath this page's rows, fetched once per request by the inline whose
    # rows have any; None means each row reads its own.
    cohort_rows_beneath: LayerRows | None = None

    def get_queryset(self, request: HttpRequest) -> models.QuerySet[DeadlineOverride]:
        rows: models.QuerySet[DeadlineOverride] = super().get_queryset(request)
        return rows.select_related(
            "site", "collection_item", "set_by", *self.parent_select_related
        )

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
        if db_field.name != "collection_item":
            return cast(
                "forms.ModelChoiceField | None",
                super().formfield_for_foreignkey(db_field, request, **kwargs),
            )
        course = self.parent_course(request)
        items = (
            ContentCollectionItem.objects.filter(
                pk__in=[i.pk for i in course.viewable_collection_items()]
            ).prefetch_related("child")
            if course is not None
            else ContentCollectionItem.objects.none()
        )
        field = cast(
            "forms.ModelChoiceField | None",
            super().formfield_for_foreignkey(
                db_field,
                request,
                form_class=CollectionItemChoiceField,
                queryset=items,
                **kwargs,
            ),
        )
        if field is not None:
            # Set after the call: unfold replaces the empty label with its own. The choices
            # are listed once here; left to the field, every row's widget would run the
            # picker query again.
            field.empty_label = "Course time limit"
            field.choices = [
                ("", field.empty_label),
                *((item.pk, field.label_from_instance(item)) for item in items),
            ]
        return field

    @admin.display(description="Content default")
    def content_default(self, obj: DeadlineOverride) -> str:
        if obj._state.adding:
            return ""
        return _value_text(content_default_for(obj), obj)

    @admin.display(description="Effective")
    def effective_value(self, obj: DeadlineOverride) -> str:
        # An override row always holds a value, so it is the effective one for its layer;
        # the column shows it as a date in the site zone or as an offset.
        if obj._state.adding:
            return ""
        return _value_text(obj.value(), obj)

    @admin.display(description="Default changed")
    def default_changed_note(self, obj: DeadlineOverride) -> str:
        if obj._state.adding:
            return ""
        beneath = canonical_beneath(obj, self.cohort_rows_beneath)
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
    parent_select_related = ("cohort_registration__course",)


class LearnerDeadlineOverrideInline(DeadlineOverrideInline):
    model = LearnerDeadlineOverride
    parent_select_related = ("course_progress__course",)

    def get_formset(
        self, request: HttpRequest, obj: object | None = None, **kwargs: object
    ) -> type[BaseInlineFormSet]:
        # One read of the record's cohort rows for every learner row's "Default changed"
        # column, as the resolver reads them; the admin makes one inline per request.
        self.cohort_rows_beneath = {}
        if isinstance(obj, CourseProgress) and obj.cohort_registration_id is not None:
            self.cohort_rows_beneath = {
                (row.cohort_registration_id, row.collection_item_id): row
                for row in CohortDeadlineOverride.objects.filter(
                    cohort_registration_id=obj.cohort_registration_id
                )
            }
        return super().get_formset(request, obj, **kwargs)


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
    for item in record.course.viewable_collection_items():
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


def _policy_value_text(value: bool | timedelta | str) -> str:
    if isinstance(value, bool):
        return "On" if value else "Off"
    if isinstance(value, timedelta):
        return str(value)
    return value.replace("_", " ").capitalize()


@admin.display(description="Effective deadline policy")
def effective_deadline_policy(
    model_admin: ModelAdmin, record: CourseProgress
) -> SafeString:
    """Each setting, its resolved value and the layer that set it, from the same resolver
    the learner pages read. Values are plain text, so every line goes through format_html."""
    if record._state.adding:
        return format_html("{}", "")
    policy = get_deadline_policy().resolve(record)
    lines = [
        (field, _policy_value_text(getattr(policy, field)), policy.sources[field])
        for field in CONFIG_FIELDS
    ]
    return format_html(
        "<ul>{}</ul>", format_html_join("", "<li>{}: {} ({})</li>", lines)
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
    CourseProgressAdmin, "effective_deadline_policy", effective_deadline_policy
)
setattr(  # noqa: B010
    CourseProgressAdmin,
    "readonly_fields",
    (
        *CourseProgressAdmin.readonly_fields,
        "effective_deadlines",
        "effective_deadline_policy",
    ),
)
setattr(  # noqa: B010
    CourseProgressAdmin,
    "fieldsets",
    (
        *CourseProgressAdmin.fieldsets,
        (
            "Deadlines",
            {"fields": ("effective_deadlines", "effective_deadline_policy")},
        ),
    ),
)


class SiteDeadlineConfigForm(ConstraintValidationFormMixin):
    # site is not a form field: SiteAwareModelAdmin fills it from the request before
    # validation, and un-excluding it here only lets the one-per-site constraint run.
    constraint_fields = ("site",)

    class Meta:
        model = SiteDeadlineConfig
        fields = list(CONFIG_FIELDS)


class _DeadlineConfigAdmin(SiteAwareModelAdmin):
    """Attributes every deadline config admin shares. Not registered itself."""

    list_display = ["__str__", *CONFIG_FIELDS]
    list_filter = list(SWITCH_FIELDS)


@admin.register(SiteDeadlineConfig)
class SiteDeadlineConfigAdmin(_DeadlineConfigAdmin):
    form = SiteDeadlineConfigForm
    list_select_related = ["site"]


@admin.register(OrganisationDeadlineConfig)
class OrganisationDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["organisation"]
    autocomplete_fields = ["organisation"]
    search_fields = ["organisation__name"]


@admin.register(CourseDeadlineConfig)
class CourseDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["course"]
    autocomplete_fields = ["course"]
    search_fields = ["course__title"]


@admin.register(CohortDeadlineConfig)
class CohortDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["cohort"]
    autocomplete_fields = ["cohort"]
    search_fields = ["cohort__name"]


@admin.register(CohortCourseRegistrationDeadlineConfig)
class CohortCourseRegistrationDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = ["cohort_registration__cohort", "cohort_registration__course"]
    autocomplete_fields = ["cohort_registration"]
    search_fields = ["cohort_registration__cohort__name"]


@admin.register(LearnerCourseRegistrationDeadlineConfig)
class LearnerCourseRegistrationDeadlineConfigAdmin(_DeadlineConfigAdmin):
    list_select_related = [
        "learner_registration__learner__user",
        "learner_registration__course",
    ]
    autocomplete_fields = ["learner_registration"]
    search_fields = ["learner_registration__learner__user__email"]
