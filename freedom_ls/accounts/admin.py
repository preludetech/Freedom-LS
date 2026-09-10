import contextlib

from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.auth.models import Group
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import LegalConsent, SiteSignupPolicy, User

# Admins for these models deny delete on their own pages so nobody can thin
# out an audit trail row by row. Erasing an account is the one path that must
# take those rows with it (their FKs to User cascade), so the User admin
# vouches for them. An app that owns such a model adds it here from its admin
# module.
USER_ERASURE_CASCADE_MODELS: set[type[Model]] = {LegalConsent}

# Unregister Django's default Group
with contextlib.suppress(NotRegistered):
    admin.site.unregister(Group)


class LegalConsentInline(admin.TabularInline):
    """Read-only display of LegalConsent rows on the User change page."""

    model = LegalConsent
    extra = 0
    can_delete = False
    _LEGAL_CONSENT_FIELDS = (
        "document_type",
        "document_version",
        "git_hash",
        "timestamp",
        "ip_address",
        "consent_method",
    )
    fields = _LEGAL_CONSENT_FIELDS
    readonly_fields = _LEGAL_CONSENT_FIELDS

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(SiteSignupPolicy)
class SiteSignupPolicyAdmin(SiteAwareModelAdmin):
    list_display = [
        "site",
        "allow_signups",
        "require_name",
        "require_terms_acceptance",
    ]
    list_filter = [
        "allow_signups",
        "require_name",
        "require_terms_acceptance",
    ]


@admin.register(LegalConsent)
class LegalConsentAdmin(SiteAwareModelAdmin):
    list_display = [
        "user",
        "document_type",
        "document_version",
        "timestamp",
        "ip_address",
    ]
    list_filter = ["document_type", "document_version"]
    search_fields = ["user__email", "git_hash"]
    readonly_fields = [
        "user",
        "document_type",
        "document_version",
        "git_hash",
        "timestamp",
        "ip_address",
        "consent_method",
    ]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(User)
class UserAdmin(SiteAwareModelAdmin):
    # Forms loaded from `unfold.forms`
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ["email", "first_name", "last_name", "is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    ordering = ["email"]
    readonly_fields = ["last_login"]
    inlines = [LegalConsentInline]

    add_fieldsets = (
        (
            None,
            {
                "fields": ("email", "password1", "password2"),
            },
        ),
        (
            "Personal info",
            {
                "fields": ("first_name", "last_name"),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Use special form during user creation"""
        defaults = {}
        if obj is None:
            defaults["form"] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    def get_deleted_objects(
        self, objs: QuerySet[User] | list[User], request: HttpRequest
    ) -> tuple[list[object], dict[str, int], set[str], list[object]]:
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        perms_needed.difference_update(
            str(model._meta.verbose_name) for model in USER_ERASURE_CASCADE_MODELS
        )
        return to_delete, model_count, perms_needed, protected


# @admin.register(SiteGroup)
# class SiteGroupAdmin(SiteAwareModelAdmin):
#     list_display = ["name"]
#     search_fields = ["name"]
#     filter_horizontal = ["permissions"]
