from unfold.admin import ModelAdmin
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm
from system_base.admin import SiteAwareModelAdmin

from .models import SiteGroup

User = get_user_model()

# Unregister Django's default Group
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(SiteAwareModelAdmin):
    # Forms loaded from `unfold.forms`
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    exclude = ["sites"]


# @admin.register(SiteGroup)
# class SiteGroupAdmin(SiteAwareModelAdmin):
#     list_display = ["name"]
#     search_fields = ["name"]
#     filter_horizontal = ["permissions"]
