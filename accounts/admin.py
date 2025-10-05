# from django.contrib import admin
# from unfold.admin import ModelAdmin

# from django.contrib.auth.models import User, Group

# admin.site.unregister(User)
# admin.site.unregister(Group)
from unfold.admin import ModelAdmin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm


User = get_user_model()
# from .models import User

# admin.site.unregister(User)
admin.site.unregister(Group)




@admin.register(User)
class UserAdmin(ModelAdmin):
    # Forms loaded from `unfold.forms`
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    exclude = ["sites"]


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass