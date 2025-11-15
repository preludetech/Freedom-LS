from django import forms

from django.contrib.auth import get_user_model

User = get_user_model()


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        # TODO: allow the user to upload a profile picture

        fields = ["first_name", "last_name"]
