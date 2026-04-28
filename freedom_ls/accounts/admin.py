import contextlib

from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from django.contrib import admin
from django.contrib.admin.exceptions import NotRegistered
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin

from .models import LegalConsent, SiteSignupPolicy

User = get_user_model()

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


# @admin.register(SiteGroup)
# class SiteGroupAdmin(SiteAwareModelAdmin):
#     list_display = ["name"]
#     search_fields = ["name"]
#     filter_horizontal = ["permissions"]
