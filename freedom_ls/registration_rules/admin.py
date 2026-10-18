from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from unfold.admin import StackedInline

from django.contrib import admin, messages
from django.contrib.admin.utils import unquote
from django.db.models import Exists, OuterRef, QuerySet
from django.db.models.fields.related import ManyToManyField
from django.forms import ModelMultipleChoiceField
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.hr_attributes.models import Department, JobTitle, Location
from freedom_ls.learner_management.admin import LearnerCourseRegistrationAdmin
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRegistration,
)
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

#: Each picker's model, so the narrowed queryset is built from the field name alone.
_PICKER_MODELS: dict[str, type[JobTitle | Department | Location]] = {
    "job_titles": JobTitle,
    "departments": Department,
    "locations": Location,
}


def _rule_id_from(object_id: str | None) -> UUID | None:
    """The rule an admin ``object_id`` names; None when absent or not a UUID."""
    if not object_id:
        return None
    try:
        return UUID(object_id)
    except ValueError:
        return None


def _picker_queryset(
    rule_id: UUID | None, field_name: str
) -> QuerySet[JobTitle | Department | Location]:
    """What one picker offers the rule being edited: the organisation's active
    entries plus the ones the rule already holds, so a deactivated entry stays
    selected and saveable."""
    model = _PICKER_MODELS[field_name]
    if rule_id is None:
        return model.objects.none()
    rule = RegistrationRule.objects.filter(pk=rule_id).first()
    if rule is None:
        return model.objects.none()
    held = model.objects.filter(registration_rule_conditions__rule_id=rule_id)
    return model.objects.for_picker(
        rule.organisation_id, list(held.values_list("pk", flat=True))
    )


class AttributeRuleConditionsInline(StackedInline):
    model = AttributeRuleConditions
    fields = [
        "job_titles",
        "departments",
        "locations",
        "organisation_start_on_or_after",
        "organisation_start_before",
        "job_title_start_on_or_after",
        "job_title_start_before",
        "department_start_on_or_after",
        "department_start_before",
        "location_start_on_or_after",
        "location_start_before",
    ]
    max_num = 1
    extra = 1
    # Emptying the pickers is how a rule is widened.
    can_delete = False
    verbose_name = "Attribute conditions"

    def formfield_for_manytomany(
        self, db_field: ManyToManyField, request: HttpRequest, **kwargs: object
    ) -> ModelMultipleChoiceField | None:
        if db_field.name in _PICKER_MODELS:
            # The rule's id comes from the URL, read per request: the inline
            # instance is shared by every request, so nothing per rule may
            # live on it.
            match = request.resolver_match
            object_id = match.kwargs.get("object_id") if match else None
            kwargs["queryset"] = _picker_queryset(
                _rule_id_from(object_id), db_field.name
            )
            kwargs["error_messages"] = {
                "invalid_choice": "Choose entries from this rule's organisation."
            }
        field: ModelMultipleChoiceField | None = super().formfield_for_manytomany(
            db_field, request, **kwargs
        )
        return field


@admin.register(RegistrationRule)
class RegistrationRuleAdmin(SiteAwareModelAdmin):
    inlines = [AttributeRuleConditionsInline]
    list_display = [
        "name",
        "organisation",
        "course",
        "is_enabled",
        "uses_inactive_entries",
        "last_evaluated_at",
    ]
    list_filter = ["organisation", "is_enabled", "course"]
    list_select_related = ["organisation", "course"]
    search_fields = ["name"]
    autocomplete_fields = ["organisation", "course"]
    readonly_fields = ["last_evaluated_at", "created_at", "updated_at"]

    def get_inlines(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> list[type[AttributeRuleConditionsInline]]:
        # The conditions need the rule's organisation to offer entries, so
        # they wait for the change page.
        return [] if obj is None else list(super().get_inlines(request, obj))

    def get_queryset(self, request: HttpRequest) -> QuerySet[RegistrationRule]:
        # One query for the changelist's "Uses inactive entries" column.
        inactive = [
            Exists(
                model.objects.filter(
                    registration_rule_conditions__rule_id=OuterRef("pk"),
                    is_active=False,
                )
            )
            for model in _PICKER_MODELS.values()
        ]
        queryset: QuerySet[RegistrationRule] = super().get_queryset(request)
        return queryset.annotate(
            uses_inactive_entries=inactive[0] | inactive[1] | inactive[2]
        )

    @admin.display(
        boolean=True,
        description="Uses inactive entries",
        ordering="uses_inactive_entries",
    )
    def uses_inactive_entries(self, obj: RegistrationRule) -> bool:
        return bool(getattr(obj, "uses_inactive_entries", False))

    def _change_form_warnings(self, obj: RegistrationRule) -> list[str]:
        """What a person editing this rule should know before they save."""
        warnings: list[str] = []
        inactive = [
            f"{entry.name} ({label})"
            for name, label in (
                ("job_titles", "job title"),
                ("departments", "department"),
                ("locations", "location"),
            )
            for entry in _PICKER_MODELS[name].objects.filter(
                registration_rule_conditions__rule_id=obj.pk, is_active=False
            )
        ]
        if inactive:
            warnings.append(
                "This rule still matches learners who hold the deactivated entries: "
                f"{', '.join(inactive)}. New learners cannot be given them."
            )
        return warnings

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        if request.method == "GET" and object_id is not None:
            obj = self.get_object(request, unquote(object_id))
            if obj is not None:
                # Warnings belong on the page a person is about to edit.
                for warning in self._change_form_warnings(obj):
                    messages.warning(request, warning)
        response: HttpResponse = super().changeform_view(
            request, object_id, form_url, extra_context
        )
        return response

    def get_fields(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> list[str]:
        # The add page takes the three things a rule cannot change afterwards.
        # Conditions and the switch wait for the change page, where the
        # organisation is known and a preview can be shown.
        if obj is None:
            return ["name", "organisation", "course"]
        return [
            "name",
            "organisation",
            "course",
            "is_enabled",
            "last_evaluated_at",
            "created_at",
            "updated_at",
        ]

    def get_readonly_fields(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> list[str]:
        readonly = list(super().get_readonly_fields(request, obj))
        # Changing either would silently retract one group and register
        # another. Staff disable the rule and make a new one instead.
        return readonly if obj is None else [*readonly, "organisation", "course"]

    def response_add(
        self,
        request: HttpRequest,
        obj: RegistrationRule,
        post_url_continue: str | None = None,
    ) -> HttpResponse:
        # Always on to the change page, where conditions are added. Forcing
        # "_continue" keeps the stock "added" message and redirect.
        post = request.POST.copy()
        post["_continue"] = "1"
        setattr(request, "POST", post)  # noqa: B010 - POST is typed read-only
        response: HttpResponse = super().response_add(request, obj, post_url_continue)
        return response

    def has_delete_permission(
        self, request: HttpRequest, obj: RegistrationRule | None = None
    ) -> bool:
        if obj is not None and obj.is_enabled:
            return False
        allowed: bool = super().has_delete_permission(request, obj)
        return allowed

    def get_deleted_objects(
        self, objs: Iterable[RegistrationRule], request: HttpRequest
    ) -> tuple[list[str], dict[str, int], set[str], list[str]]:
        # A list from the single-object view, a queryset from the bulk action.
        # Enabled rules are reported as protected, which makes the confirmation
        # page refuse the selection and name them.
        rules = list(objs)
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(
            [rule for rule in rules if not rule.is_enabled], request
        )
        enabled = [f"Enabled rule: {rule.name}" for rule in rules if rule.is_enabled]
        return to_delete, model_count, perms_needed, [*protected, *enabled]


@admin.display(description="Registration rule")
def registration_rule(
    self: SiteAwareModelAdmin, obj: LearnerCourseRegistration
) -> str | SafeString:
    """The rule that made this registration; blank for a staff- or learner-made one."""
    link = (
        RuleRegistration.objects.filter(registration_id=obj.pk)
        .select_related("rule")
        .first()
    )
    if link is None:
        return ""
    if link.rule is None:
        return f"{link.rule_name} (deleted)"
    return format_html(
        '<a href="{}">{}</a>',
        reverse(
            "admin:freedom_ls_registration_rules_registrationrule_change",
            args=[link.rule.pk],
        ),
        link.rule.name,
    )


# The rule's name on a registration's own change page, through the attributes
# LearnerCourseRegistrationAdmin declares. The wiring runs from here rather
# than from learner_management, which must stay installable without this app.
# Appending keeps every field another app has already contributed.
setattr(  # noqa: B010 - the function binds as a method of the admin class
    LearnerCourseRegistrationAdmin, "registration_rule", registration_rule
)
LearnerCourseRegistrationAdmin.readonly_fields = [
    *LearnerCourseRegistrationAdmin.readonly_fields,
    "registration_rule",
]
_first, *_rest = LearnerCourseRegistrationAdmin.fieldsets
_fieldsets = (
    (_first[0], {**_first[1], "fields": (*_first[1]["fields"], "registration_rule")}),
    *_rest,
)
setattr(LearnerCourseRegistrationAdmin, "fieldsets", _fieldsets)  # noqa: B010
