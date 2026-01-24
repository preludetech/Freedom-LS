from typing import Any
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Model
from django.forms import ModelForm
from django.http import HttpRequest
from guardian.admin import GuardedModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from .models import SiteGroup

User = get_user_model()

# Unregister Django's default Group
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass


@admin.register(SiteGroup)
class SiteGroupAdmin(SiteAwareModelAdmin, GuardedModelAdmin):
    list_display = ["group_name"]

    search_fields = ["group_name"]
    filter_horizontal = ["permissions"]

    exclude = ["name", "site"]

    def save_model(
        self,
        request: HttpRequest,
        obj: SiteGroup,
        form: ModelForm,
        change: bool
    ) -> None:
        # Ensure site is set from request if not already set
        if not obj.site_id:
            obj.site = get_current_site(request)

        super().save_model(request, obj, form, change)


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

    filter_horizontal = ("groups", "user_permissions")

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
