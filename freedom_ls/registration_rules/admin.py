from __future__ import annotations

from collections.abc import Iterable, Mapping
from uuid import UUID

from unfold.admin import StackedInline

from django.contrib import admin, messages
from django.contrib.admin.options import csrf_protect_m
from django.contrib.admin.utils import unquote
from django.db.models import (
    BooleanField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    QuerySet,
)
from django.db.models.fields.related import ManyToManyField
from django.forms import ModelMultipleChoiceField, all_valid
from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.content_engine.models import CourseVisibility
from freedom_ls.hr_attributes.admin import ListEntryAdmin
from freedom_ls.hr_attributes.models import Department, JobTitle, Location
from freedom_ls.learner_management.admin import LearnerCourseRegistrationAdmin
from freedom_ls.learner_management.models import (
    Learner,
    LearnerCourseRegistration,
)
from freedom_ls.registration_rules.evaluation import (
    classify_rule_changes,
    rules_enabled_for,
)
from freedom_ls.registration_rules.kinds import RuleState
from freedom_ls.registration_rules.loader import get_rule_kind
from freedom_ls.registration_rules.models import (
    AttributeRuleConditions,
    RegistrationRule,
    RuleRegistration,
    rules_naming,
)
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin, admin_page_context

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
        "change_not_yet_applied",
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
        # One query for the changelist's "Uses inactive entries" column. The
        # "Change not yet applied" column and the change form's warning share
        # one predicate.
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
            uses_inactive_entries=inactive[0] | inactive[1] | inactive[2],
            change_not_yet_applied=ExpressionWrapper(
                Q(is_enabled=True)
                & (
                    Q(last_evaluated_at__isnull=True)
                    | Q(last_evaluated_at__lt=F("updated_at"))
                ),
                output_field=BooleanField(),
            ),
        )

    @admin.display(
        boolean=True,
        description="Uses inactive entries",
        ordering="uses_inactive_entries",
    )
    def uses_inactive_entries(self, obj: RegistrationRule) -> bool:
        return bool(getattr(obj, "uses_inactive_entries", False))

    @admin.display(
        boolean=True,
        description="Change not yet applied",
        ordering="change_not_yet_applied",
    )
    def change_not_yet_applied(self, obj: RegistrationRule) -> bool:
        return bool(getattr(obj, "change_not_yet_applied", False))

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
        if obj.course.visibility != CourseVisibility.PUBLISHED:
            warnings.append(
                "This course is not published. The rule still registers learners, "
                "who will not see it until it is."
            )
        if getattr(obj, "change_not_yet_applied", False):
            if not rules_enabled_for(obj.organisation_id):
                warnings.append(
                    f"Registration rules are switched off for {obj.organisation}; "
                    "this rule's changes apply once they are switched on."
                )
            else:
                warnings.append(
                    "This rule's last change has not been applied yet. "
                    "The task is queued or has failed; check the task worker."
                )
        return warnings

    def _stock_changeform(
        self,
        request: HttpRequest,
        object_id: str | None,
        form_url: str,
        extra_context: dict[str, object] | None,
    ) -> HttpResponse:
        response: HttpResponse = super().changeform_view(
            request, object_id, form_url, extra_context
        )
        return response

    @csrf_protect_m
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
        if (
            request.method != "POST"
            or object_id is None
            or "_confirmed" in request.POST
        ):
            return self._stock_changeform(request, object_id, form_url, extra_context)
        rule = self.get_object(request, unquote(object_id))
        if rule is None or not self.has_change_permission(request, rule):
            # The stock view answers both cases: a redirect for a missing
            # object, a 403 for a forbidden one.
            return self._stock_changeform(request, object_id, form_url, extra_context)
        enabled_before = rule.is_enabled
        model_form = self.get_form(request, rule, change=True)
        form = model_form(request.POST, request.FILES, instance=rule)
        if not form.is_valid():
            return self._stock_changeform(request, object_id, form_url, extra_context)
        # is_valid() has written the submitted values onto `rule`; the saved
        # values are now only in the database.
        formsets, _ = self._create_formsets(request, rule, change=True)
        if not all_valid(formsets):
            return self._stock_changeform(request, object_id, form_url, extra_context)
        if not (enabled_before or rule.is_enabled):
            # Disabled before and after: nothing can change for any learner.
            return self._stock_changeform(request, object_id, form_url, extra_context)
        # A user who may only view the conditions posts none of them; Django
        # then sets the inline form's cleaned_data to its stored initial values,
        # so the preview still reads the saved conditions. Without the inline
        # at all, the preview reads them from the rule.
        conditions_form = (
            formsets[0].forms[0] if formsets and formsets[0].forms else None
        )
        cleaned = conditions_form.cleaned_data if conditions_form else None
        return self._render_preview(request, rule, cleaned, form_url)

    def _render_preview(
        self,
        request: HttpRequest,
        rule: RegistrationRule,
        cleaned: Mapping[str, object] | None,
        form_url: str,
    ) -> HttpResponse:
        """The confirmation page: who a save would register, retract or keep."""
        # The saved rule is re-read so ownership comes from the database
        # while the match comes from the submission.
        saved = RegistrationRule.objects.select_related("organisation", "course").get(
            pk=rule.pk
        )
        kind = get_rule_kind(saved.kind)
        submitted = RuleState(
            site_id=saved.site_id,
            organisation_id=saved.organisation_id,
            course_id=saved.course_id,
            is_enabled=rule.is_enabled,
            conditions=(
                kind.conditions_from_rule(saved)
                if cleaned is None
                else kind.conditions_from_cleaned_data(cleaned)
            ),
        )
        changes = classify_rule_changes(saved, submitted)
        # The lists name people. Counts are enough for someone allowed to run
        # rules but not to look at learners.
        can_view_learners = request.user.has_perm(
            "freedom_ls_learner_management.view_learner"
        )
        learner_ids = {
            *changes.register,
            *changes.reactivate,
            *changes.retract,
            *changes.kept_started,
            *(handed.learner_id for handed in changes.hand_over),
        }
        learners = (
            {
                learner.pk: learner
                for learner in Learner.objects.filter(
                    pk__in=learner_ids
                ).select_related("user")
            }
            if can_view_learners
            else {}
        )
        context = {
            "rule": saved,
            "can_view_learners": can_view_learners,
            "will_register": [
                learners.get(pk) for pk in (*changes.register, *changes.reactivate)
            ],
            "will_retract": [learners.get(pk) for pk in changes.retract],
            "stays_registered": [
                *(
                    (learners.get(pk), "Started the course")
                    for pk in changes.kept_started
                ),
                *(
                    (learners.get(h.learner_id), f"Still matched by {h.rule_name}")
                    for h in changes.hand_over
                ),
            ],
            "switch_is_off": not rules_enabled_for(saved.organisation_id),
            "posted": [
                (name, value)
                for name in request.POST
                if name != "csrfmiddlewaretoken"
                for value in request.POST.getlist(name)
            ],
            "form_url": form_url or request.path,
            **admin_page_context(request, self, f"Confirm changes to {saved.name}"),
        }
        return TemplateResponse(
            request, "admin/registration_rules/preview.html", context
        )

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


_list_entry_deleted_objects = ListEntryAdmin.get_deleted_objects


def _list_entry_deleted_objects_naming_rules(
    self: ListEntryAdmin,
    objs: Iterable[JobTitle | Department | Location],
    request: HttpRequest,
) -> tuple[list[str], dict[str, int], set[str], list[str]]:
    """The stock delete confirmation, refusing entries a rule names.

    The delete itself is refused by a pre_delete receiver; listing the rules
    as protected makes the confirmation page say so instead of failing.
    """
    entries = list(objs)
    to_delete, model_count, perms_needed, protected = _list_entry_deleted_objects(
        self, entries, request
    )
    named = [
        f"Registration rule: {rule.name}"
        for entry in entries
        for rule in rules_naming(entry)
    ]
    return to_delete, model_count, perms_needed, [*protected, *named]


# Wired from here for the same reason as the registration admin above.
setattr(  # noqa: B010 - the function binds as a method of the admin class
    ListEntryAdmin, "get_deleted_objects", _list_entry_deleted_objects_naming_rules
)
