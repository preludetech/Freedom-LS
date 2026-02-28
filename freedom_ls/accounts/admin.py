from django.contrib import admin
from unfold.admin import TabularInline

from typing import Any
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.contrib.sites.shortcuts import get_current_site
from django.db.models import Model
from django.forms import ModelForm, ModelChoiceField
from django.http import HttpRequest
from django.contrib.admin.widgets import FilteredSelectMultiple
from django import forms
from django.utils.translation import gettext_lazy as _
from guardian.admin import GuardedModelAdmin, AdminGroupObjectPermissionsForm
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from freedom_ls.site_aware_models.admin import SiteAwareModelAdmin
from .models import SiteGroup


class SiteAwareGroupSelectForm(forms.Form):
    """
    Replaces the default GroupManage CharField with a site-filtered
    ModelChoiceField dropdown so users pick by group_name, not internal name.
    """
    group = forms.ModelChoiceField(
        queryset=SiteGroup.objects.none(),
        label=_("Group"),
        empty_label=_("Select a group..."),
    )

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = SiteGroup.objects.filter(site=site) if site else SiteGroup.objects.all()
        self.fields["group"].queryset = qs


class SiteAwareGroupObjectPermissionsForm(AdminGroupObjectPermissionsForm):
    """
    Replaces the group field with a site-filtered dropdown showing
    group_name labels (e.g. "Group 1") instead of the internal name
    (e.g. "Group 1 (127.0.0.1:8000)").
    """

    def __init__(self, *args, site=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = SiteGroup.objects.filter(site=site) if site else SiteGroup.objects.all()
        self.fields["group"] = forms.ModelChoiceField(
            queryset=qs,
            label=_("Group"),
            required=False,
        )

    def get_obj_perms_field_widget(self):
        return FilteredSelectMultiple(_("Permissions"), False)


class SiteAwareGuardedModelAdminMixin:
    """
    Mixin for any GuardedModelAdmin subclass that needs the group
    object permissions form to be filtered to the current site.

    Usage:
        class MyCohortAdmin(SiteAwareGuardedModelAdminMixin, GuardedModelAdmin):
            ...
    """

    def get_obj_perms_group_select_form(self, request):
        """Override the initial group-picker form (the search bar) with a dropdown."""
        site = get_current_site(request)

        class BoundSelectForm(SiteAwareGroupSelectForm):
            def __init__(self_, *args, **kwargs):
                kwargs.setdefault("site", site)
                super().__init__(*args, **kwargs)

        return BoundSelectForm

    def get_obj_perms_manage_group_form(self, request):
        """Override the group permissions management form with a site-filtered dropdown."""
        site = get_current_site(request)

        class BoundForm(SiteAwareGroupObjectPermissionsForm):
            def __init__(self_, *args, **kwargs):
                kwargs.setdefault("site", site)
                super().__init__(*args, **kwargs)

        return BoundForm

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
