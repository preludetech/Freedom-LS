from __future__ import annotations

from collections.abc import Iterable

from django.contrib import admin
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString

from freedom_ls.learner_management.admin import LearnerCourseRegistrationAdmin
from freedom_ls.learner_management.models import LearnerCourseRegistration
from freedom_ls.registration_rules.models import RegistrationRule, RuleRegistration
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin


@admin.register(RegistrationRule)
class RegistrationRuleAdmin(SiteAwareModelAdmin):
    list_display = ["name", "organisation", "course", "is_enabled", "last_evaluated_at"]
    list_filter = ["organisation", "is_enabled", "course"]
    list_select_related = ["organisation", "course"]
    search_fields = ["name"]
    autocomplete_fields = ["organisation", "course"]
    readonly_fields = ["last_evaluated_at", "created_at", "updated_at"]

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
